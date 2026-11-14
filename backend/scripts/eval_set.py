"""评测集跑分：问题样本算召回，示范文本算误报（文档 6.3）。

用法：
    python -m scripts.eval_set                # 全部样本
    python -m scripts.eval_set --only prepaid # 只跑某一类
    python -m scripts.eval_set --reuse        # 复用上次结果，不重新调用模型
    python -m scripts.eval_set --markdown docs/评测结果.md

标注口径见 tests/fixtures/samples/eval/labels.json：
- expected  必须命中的审查项（计入召回分母）
- optional  命中加分、不命中不扣分（不计入分母）
- not_expected  明确不该命中的项；fair 组任何 high/medium 都记误报
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.services.agent import run_review
from app.services.parsing import detect, parse_pdf, split_clauses

EVAL_DIR = Path(__file__).parents[1] / "tests" / "fixtures" / "samples" / "eval"
LABELS = EVAL_DIR / "labels.json"
CACHE = Path(__file__).parents[1] / "data" / "eval_cache.json"

HIT_LEVELS = {"high", "medium"}
LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}


@dataclass
class SampleResult:
    file: str
    group: str
    contract_type: str
    title: str
    clause_count: int
    safety_score: int | None
    elapsed: float
    found: dict[str, str] = field(default_factory=dict)  # item_id -> risk_level
    missed: list[str] = field(default_factory=list)
    optional_hit: list[str] = field(default_factory=list)
    false_positives: list[dict] = field(default_factory=list)
    raw_findings: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "file": self.file,
            "group": self.group,
            "contract_type": self.contract_type,
            "title": self.title,
            "clause_count": self.clause_count,
            "safety_score": self.safety_score,
            "elapsed": round(self.elapsed, 1),
            "found": self.found,
            "missed": self.missed,
            "optional_hit": self.optional_hit,
            "false_positives": self.false_positives,
            "raw_findings": self.raw_findings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SampleResult":
        return cls(**data)


async def run_one(spec: dict) -> SampleResult:
    path = (EVAL_DIR / spec["file"]).resolve()
    parsed = parse_pdf(path)
    clauses = split_clauses(parsed)
    detection = detect(parsed.full_text)

    started = time.perf_counter()
    done: dict = {}
    async for event in run_review(
        clauses=clauses,
        full_text=parsed.full_text,
        contract_type=spec["contract_type"],
    ):
        if event["event"] == "done":
            done = event["data"]
    elapsed = time.perf_counter() - started

    findings = done.get("findings", [])
    result = SampleResult(
        file=spec["file"],
        group=spec["group"],
        contract_type=spec["contract_type"],
        title=spec["title"],
        clause_count=len(clauses),
        safety_score=done.get("safety_score"),
        elapsed=elapsed,
        raw_findings=[
            {
                "item_id": f.get("item_id"),
                "risk_level": f.get("risk_level"),
                "title": f.get("title"),
                "clause_no": f.get("clause_no"),
                "needs_review": f.get("needs_review"),
            }
            for f in findings
        ],
    )

    # 同一 item 可能被多条条款各命中一次，取最高风险等级
    for f in findings:
        item_id = f.get("item_id") or ""
        level = f.get("risk_level") or "none"
        if not item_id:
            continue
        prev = result.found.get(item_id)
        if prev is None or LEVEL_ORDER.get(level, 9) < LEVEL_ORDER.get(prev, 9):
            result.found[item_id] = level

    if spec["group"] == "problem":
        for exp in spec.get("expected", []):
            level = result.found.get(exp["item_id"], "none")
            if level not in HIT_LEVELS:
                result.missed.append(exp["item_id"])
        for opt in spec.get("optional", []):
            if result.found.get(opt["item_id"], "none") in HIT_LEVELS:
                result.optional_hit.append(opt["item_id"])
    else:
        for f in findings:
            if (f.get("risk_level") or "none") in HIT_LEVELS:
                result.false_positives.append(
                    {
                        "item_id": f.get("item_id"),
                        "risk_level": f.get("risk_level"),
                        "title": f.get("title"),
                        "clause_no": f.get("clause_no"),
                    }
                )
    return result


def summarize(results: list[SampleResult], labels: dict) -> dict:
    by_file = {s["file"]: s for s in labels["samples"]}
    problem = [r for r in results if r.group == "problem"]
    fair = [r for r in results if r.group == "fair"]

    def recall(level: str | None) -> tuple[int, int]:
        hit = total = 0
        for r in problem:
            spec = by_file[r.file]
            for exp in spec.get("expected", []):
                if level and exp["risk_level"] != level:
                    continue
                total += 1
                if r.found.get(exp["item_id"], "none") in HIT_LEVELS:
                    hit += 1
        return hit, total

    all_hit, all_total = recall(None)
    high_hit, high_total = recall("high")
    med_hit, med_total = recall("medium")
    fp_count = sum(len(r.false_positives) for r in fair)
    fair_clauses = sum(r.clause_count for r in fair)

    return {
        "problem_samples": len(problem),
        "fair_samples": len(fair),
        "recall_all": (all_hit, all_total),
        "recall_high": (high_hit, high_total),
        "recall_medium": (med_hit, med_total),
        "false_positive": fp_count,
        "fair_clauses": fair_clauses,
        "fp_rate": (fp_count / fair_clauses) if fair_clauses else 0.0,
        "avg_elapsed": sum(r.elapsed for r in results) / len(results) if results else 0.0,
    }


def to_markdown(results: list[SampleResult], stat: dict, labels: dict) -> str:
    by_file = {s["file"]: s for s in labels["samples"]}
    lines = ["# 评测集跑分结果", ""]
    lines.append(
        f"问题样本 {stat['problem_samples']} 份，对照（示范文本）{stat['fair_samples']} 份，"
        f"平均单份耗时 {stat['avg_elapsed']:.1f}s。"
    )
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 指标 | 结果 |")
    lines.append("|---|---|")
    ah, at = stat["recall_all"]
    hh, ht = stat["recall_high"]
    mh, mt = stat["recall_medium"]
    lines.append(f"| 全部关注项召回 | {ah}/{at} = {ah / at * 100:.1f}% |" if at else "| 全部关注项召回 | - |")
    lines.append(f"| 其中高风险召回 | {hh}/{ht} = {hh / ht * 100:.1f}% |" if ht else "| 其中高风险召回 | - |")
    lines.append(f"| 其中中风险召回 | {mh}/{mt} = {mh / mt * 100:.1f}% |" if mt else "| 其中中风险召回 | - |")
    lines.append(
        f"| 示范文本误报 | {stat['false_positive']} 条 / {stat['fair_clauses']} 条款"
        f"（{stat['fp_rate'] * 100:.1f}%） |"
    )
    lines.append("")
    lines.append("## 逐份明细")
    lines.append("")
    lines.append("| 样本 | 类型 | 条款 | 安全分 | 命中 | 漏报 | 耗时 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        exp = by_file[r.file].get("expected", [])
        hit = sum(1 for e in exp if r.found.get(e["item_id"], "none") in HIT_LEVELS)
        lines.append(
            f"| {r.title} | {r.contract_type} | {r.clause_count} | {r.safety_score} | "
            f"{hit}/{len(exp)} | {'、'.join(r.missed) or '—'} | {r.elapsed:.1f}s |"
        )
    lines.append("")
    for r in results:
        if r.group != "problem" or not r.missed:
            continue
        spec = by_file[r.file]
        lines.append(f"### 漏报：{r.title}")
        lines.append("")
        for e in spec.get("expected", []):
            if e["item_id"] in r.missed:
                lines.append(f"- **{e['item_id']}**（{e['risk_level']}）{e['point']}")
        lines.append("")

    fair = [r for r in results if r.group == "fair"]
    if fair:
        lines.append("## 对照组误报明细")
        lines.append("")
        lines.append("示范文本是**未填写**的模板，空白处被判为「未约定」属口径问题，已由空白模板识别降级；"
                     "仍判为中风险的部分逐条列出。")
        lines.append("")
        for r in fair:
            if not r.false_positives:
                continue
            lines.append(f"**{r.title}**（安全分 {r.safety_score}）")
            lines.append("")
            for f in r.false_positives:
                lines.append(f"- {f['item_id']} {f['risk_level']} · {f['clause_no']} · {f['title']}")
            lines.append("")

    lines.append("## 样本来源")
    lines.append("")
    lines.append("| 样本 | 组别 | 来源 |")
    lines.append("|---|---|---|")
    for r in results:
        spec = by_file[r.file]
        lines.append(f"| {r.title} | {r.group} | {spec.get('provenance', '')} |")
    lines.append("")
    lines.append("## 口径")
    lines.append("")
    lines.append("- **召回**：`labels.json` 中 `expected` 项被判为 high 或 medium 即算命中，按等级分层统计。")
    lines.append("- **optional**：命中加分、不命中不扣分，不计入召回分母。")
    lines.append("- **误报**：仅以对照组的官方示范文本为分母；问题样本上的额外发现不记为误报（可能确实是漏标的问题）。")
    lines.append("- **空白模板**：平均每条款填空标记 ≥ 2 处即判定为未填写的模板，中风险结论降为低风险并标注需复核，"
                 "高风险不受影响（见 `app/services/agent/tools.py`）。")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="只跑指定合同类型：lease / labor / prepaid")
    parser.add_argument("--reuse", action="store_true", help="复用上次结果，不重新调用模型")
    parser.add_argument("--markdown", default="", help="把结果写成 markdown 文件的路径")
    args = parser.parse_args()

    labels = json.loads(LABELS.read_text("utf-8"))
    specs = [s for s in labels["samples"] if not args.only or s["contract_type"] == args.only]

    results: list[SampleResult] = []
    if args.reuse and CACHE.is_file():
        cached = {r["file"]: r for r in json.loads(CACHE.read_text("utf-8"))}
        results = [SampleResult.from_dict(cached[s["file"]]) for s in specs if s["file"] in cached]
        print(f"复用缓存 {len(results)} 份")
    if len(results) < len(specs):
        done_files = {r.file for r in results}
        for spec in specs:
            if spec["file"] in done_files:
                continue
            print(f"→ {spec['title']} ({spec['file']})", flush=True)
            r = await run_one(spec)
            print(
                f"  条款 {r.clause_count} | 安全分 {r.safety_score} | "
                f"命中 {len(r.found)} 项 | 漏报 {len(r.missed)} 项 | {r.elapsed:.1f}s",
                flush=True,
            )
            results.append(r)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(
            json.dumps([r.as_dict() for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    stat = summarize(results, labels)
    ah, at = stat["recall_all"]
    hh, ht = stat["recall_high"]
    mh, mt = stat["recall_medium"]
    print("-" * 78)
    print(f"全部关注项召回 {ah}/{at}" + (f" = {ah / at * 100:.1f}%" if at else ""))
    print(f"高风险召回     {hh}/{ht}" + (f" = {hh / ht * 100:.1f}%" if ht else ""))
    print(f"中风险召回     {mh}/{mt}" + (f" = {mh / mt * 100:.1f}%" if mt else ""))
    print(f"示范文本误报   {stat['false_positive']} 条 / {stat['fair_clauses']} 条款")
    print(f"平均耗时       {stat['avg_elapsed']:.1f}s")

    missed_total = [f"{r.title}: {','.join(r.missed)}" for r in results if r.missed]
    if missed_total:
        print("-" * 78)
        for line in missed_total:
            print(f"漏报 {line}")

    if args.markdown:
        out = Path(args.markdown)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(results, stat, labels), encoding="utf-8")
        print(f"已写入 {out}")


if __name__ == "__main__":
    asyncio.run(main())
