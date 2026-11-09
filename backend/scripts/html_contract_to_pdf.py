"""把网页/纯文本形式的合同示范文本转成可解析的 PDF。

用途：政府网站上的示范文本多为 HTML 或 .doc，PyMuPDF 无法直接读取。
本脚本提供一条确定的转换路径，产出**版式简化、但条文结构完整**的 PDF，
用于开发期自测与回归；它不能替代真实已签署合同的版式验证。

用法：
    python -m scripts.html_contract_to_pdf <输入.html|.txt> <输出.pdf> [--title 合同标题]
"""

from __future__ import annotations

import argparse
import html
import re
import zipfile
from pathlib import Path

import pymupdf

PAGE_W, PAGE_H = 595, 842
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 64, 72, 72
FONT, FONT_SIZE, LINE_HEIGHT = "china-s", 10.5, 17.0
# 中文全角，单字宽度≈字号，可用宽度 595-128=467pt → 约 44 字/行
MAX_CHARS = 43

BLOCK_TAGS = (
    "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", raw)
    for tag in BLOCK_TAGS:
        raw = re.sub(rf"(?i)</?{tag}[^>]*>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", "", raw)
    text = html.unescape(raw)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def docx_to_text(path: Path) -> str:
    """从 .docx 提取段落文本（zip + document.xml，不依赖 python-docx）。"""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"<w:(br|cr)[^>]*/>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", " ", xml)
    xml = xml.replace("</w:p>", "\n")
    xml = re.sub(r"(?s)<[^>]+>", "", xml)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in html.unescape(xml).splitlines()]
    return "\n".join(ln for ln in lines if ln)


def wrap(line: str, width: int = MAX_CHARS) -> list[str]:
    if len(line) <= width:
        return [line]
    return [line[i : i + width] for i in range(0, len(line), width)]


def render(text: str, out_path: Path, title: str | None = None) -> int:
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = MARGIN_TOP
    pages = 1

    def new_page() -> None:
        nonlocal page, y, pages
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        y = MARGIN_TOP
        pages += 1

    if title:
        page.insert_text((MARGIN_X, y), title, fontname=FONT, fontsize=14)
        y += LINE_HEIGHT * 1.6

    for logical in text.splitlines():
        for piece in wrap(logical):
            if y > PAGE_H - MARGIN_BOTTOM:
                new_page()
            page.insert_text((MARGIN_X, y), piece, fontname=FONT, fontsize=FONT_SIZE)
            y += LINE_HEIGHT

    doc.save(out_path)
    doc.close()
    return pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    raw = args.source.read_text(encoding="utf-8", errors="ignore")
    suffix = args.source.suffix.lower()
    if suffix in {".html", ".htm"}:
        text = html_to_text(raw)
    elif suffix == ".docx":
        text = docx_to_text(args.source)
    else:
        text = raw
    pages = render(text, args.target, args.title)
    print(f"生成 {args.target}，{pages} 页，{len(text)} 字")


if __name__ == "__main__":
    main()
