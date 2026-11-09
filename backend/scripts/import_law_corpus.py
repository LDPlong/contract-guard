"""把法规原文网页导入为语料文件（app/data/corpus/*.md）。

背景：官方站点（npc.gov.cn / flk.npc.gov.cn）正文为 JS 渲染或分页连载，
本脚本按"权威转载页 + 分页抓取"的方式取全文，逐条切分后落成可入库的 Markdown。

输出格式：
    # 中华人民共和国民法典
    <!-- source: 民法典 | version: 2020-05-28 通过 | effective: 2021-01-01 | fetched: 2026-11-10 -->

    ## 第一条
    为了保护民事主体的合法权益……

用法：
    python -m scripts.import_law_corpus            # 抓取全部并写入
    python -m scripts.import_law_corpus --check    # 只校验不写盘
"""

from __future__ import annotations

import argparse
import html
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

CORPUS_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "corpus"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

ARTICLE_RE = re.compile(r"第([一二三四五六七八九十百千零〇两]+)条")
HEADER = re.compile(r"^\s*第([一二三四五六七八九十百千零〇两]+)条\s*")

# 政府网站正文末尾的导航/版权噪声，逐行过滤（只删短行，避免误伤正文）
NOISE = (
    "打印", "关闭", "关于我们", "地图导航", "联系方式", "免责声明", "使用帮助",
    "主办", "电话：", "粤ICP", "粤公网安备", "网站标识码", "Copyright", "-->",
    "扫一扫", "分享到", "上一篇", "下一篇", "字体：",
)


@dataclass
class Source:
    key: str
    title: str
    source: str
    version: str
    effective: str
    urls: list[str]
    expect_last: str = ""  # 期望出现在正文的最后一条，用于校验完整性
    local_html: Path | None = None
    notes: list[str] = field(default_factory=list)


CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(text: str) -> int | None:
    """中文数字转整数，仅支持 1~9999（法条编号范围足够）。"""
    total, section, number = 0, 0, 0
    for ch in text:
        if ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            section += (number or 1) * unit
            number = 0
        else:
            return None
    return total + section + number


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|td|tr|li|h\d)>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", "", raw)
    text = html.unescape(raw).replace("\u3000", " ").replace("\xa0", " ")
    return text


def extract_articles(text: str) -> dict[int, str]:
    """按"第X条"切分，返回 {条号: 正文}。同号保留首次出现（分页会有重叠）。

    注意：必须先筛出**行首**的编号再切片。否则正文里的"依据本法第五百一十条"这类
    引用会被当成下一条的起点，把真正的条文截断（劳动合同法第 25 条就踩过这个坑）。
    """
    starts = []
    for match in ARTICLE_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        if not text[line_start : match.start()].strip():
            starts.append(match)

    articles: dict[int, str] = {}
    for idx, match in enumerate(starts):
        number = cn_to_int(match.group(1))
        if number is None or number in articles:
            continue
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        body = text[match.end() : end]
        body = re.sub(r"[ \t]+", " ", body)
        body = re.sub(r"\n{2,}", "\n", body).strip()
        body = body.rstrip("-—　 ")
        body = "\n".join(
            ln for ln in body.split("\n") if not (len(ln.strip()) <= 30 and ln.strip().startswith(NOISE))
        )
        if len(body) >= 4:
            articles[number] = body
    return articles


def fetch(url: str, client: httpx.Client, retries: int = 3) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url)
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return html_to_text(resp.text)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.2 * (attempt + 1))
    print(f"  ! 抓取失败 {url} ({type(last).__name__})")
    return ""


def build_source(source: Source, client: httpx.Client) -> dict[int, str]:
    merged: dict[int, str] = {}
    if source.local_html and source.local_html.exists():
        merged.update(extract_articles(html_to_text(source.local_html.read_text("utf-8", "ignore"))))
    for url in source.urls:
        text = fetch(url, client)
        if not text:
            continue
        for number, body in extract_articles(text).items():
            merged.setdefault(number, body)
        time.sleep(0.25)
    return merged


def render(source: Source, articles: dict[int, str]) -> str:
    lines = [
        f"# {source.title}",
        f"<!-- source: {source.source} | version: {source.version} "
        f"| effective: {source.effective} | fetched: {date.today().isoformat()} -->",
        "",
    ]
    for number in sorted(articles):
        lines.append(f"## 第{number_to_cn(number)}条")
        lines.append(articles[number])
        lines.append("")
    return "\n".join(lines)


CN = "零一二三四五六七八九"
CN_UNIT_POS = ["", "十", "百", "千"]


def number_to_cn(number: int) -> str:
    """整数转中文条号，符合法条书写规范：716 → 七百一十六，16 → 十六，1105 → 一千一百零五。"""
    if number <= 0:
        return CN[0]

    raw = str(number)
    parts: list[str] = []
    pending_zero = False
    for idx, ch in enumerate(raw):
        digit = int(ch)
        pos = len(raw) - idx - 1
        if digit == 0:
            pending_zero = True
            continue
        if pending_zero and parts:
            parts.append("零")
        pending_zero = False
        parts.append(CN[digit] + CN_UNIT_POS[pos])
    text = "".join(parts)

    # 十位起头省略"一"（16 → 十六），但与更高位组合时保留（716 → 七百一十六）
    if text.startswith("一十"):
        text = text[1:]
    return text


SOURCES = [
    Source(
        key="civil_code",
        title="中华人民共和国民法典",
        source="民法典",
        version="2020-05-28 通过",
        effective="2021-01-01",
        urls=[
            "https://www.rmzxw.com.cn/c/2020-06-01/2587006.shtml",
            *[f"https://www.rmzxw.com.cn/c/2020-06-01/2587006_{i}.shtml" for i in range(1, 40)],
        ],
        expect_last="第一千二百六十条",
    ),
    Source(
        key="labor_contract_law",
        title="中华人民共和国劳动合同法",
        source="劳动合同法",
        version="2012-12-28 修正",
        effective="2013-07-01",
        urls=[],
        local_html=RAW_DIR / "labor_law.html",
        expect_last="第九十八条",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = parser.parse_args()

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        timeout=40, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
    ) as client:
        for source in SOURCES:
            print(f"[{source.key}] 抓取中…")
            articles = build_source(source, client)
            numbers = sorted(articles)
            print(f"  条目 {len(articles)}，范围 {numbers[0] if numbers else '-'} ~ {numbers[-1] if numbers else '-'}")

            if source.expect_last:
                last_no = cn_to_int(source.expect_last[len("第") : -len("条")])
                if last_no and last_no not in articles:
                    print(f"  ! 缺少 {source.expect_last}，可能有分页未取全")

            if args.check:
                continue
            path = CORPUS_DIR / f"{source.key}.md"
            path.write_text(render(source, articles), encoding="utf-8")
            print(f"  -> {path.relative_to(CORPUS_DIR.parents[2])}, {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
