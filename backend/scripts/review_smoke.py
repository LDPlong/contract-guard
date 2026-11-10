"""端到端审查冒烟：真实合同 → 切分 → 预筛 → LLM 判定 → 汇总。

用法：
    python -m scripts.review_smoke [样本 pdf 路径]
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from app.services.agent import run_review
from app.services.parsing import detect, parse_pdf, split_clauses

DEFAULT_SAMPLE = Path(__file__).parents[1] / "tests" / "fixtures" / "samples" / "lease_gd.pdf"


async def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE
    parsed = parse_pdf(path)
    clauses = split_clauses(parsed)
    detection = detect(parsed.full_text)

    print(f"文件={path.name} 页={parsed.page_count} 条款={len(clauses)} "
          f"类型={detection.contract_type}/{detection.source}")
    print("-" * 78)

    started = time.perf_counter()
    done_payload: dict = {}

    async for event in run_review(
        clauses=clauses,
        full_text=parsed.full_text,
        contract_type=detection.contract_type,
    ):
        kind = event["event"]
        data = event["data"]
        if kind == "step":
            print(f"[{data['step']:<8}] {data['message']}")
        elif kind == "finding":
            print(f"  ! {data['risk_level']:<6} {data['title']}")
        elif kind == "done":
            done_payload = data

    elapsed = time.perf_counter() - started
    print("-" * 78)
    findings = done_payload.get("findings", [])
    print(f"安全分 {done_payload.get('safety_score')} | {done_payload.get('summary')}")
    print(f"耗时 {elapsed:.1f}s | 需复核 {done_payload.get('needs_review')} 项 | "
          f"跳过 {len(done_payload.get('skipped_items', []))} 项")

    for f in findings:
        basis = (
            "、".join(f"{b.get('source', '')} {b.get('article', '')}".strip() for b in f.get("legal_basis", []))
            or "（无依据）"
        )
        print(f"\n[{f['risk_level']}] {f['title']}  ({f['category']}, conf={f['confidence']})")
        print(f"  条款: {f.get('clause_no')} p{f.get('page_no')}")
        print(f"  理由: {f['reason']}")
        print(f"  依据: {basis}")
        print(f"  建议: {f['suggestion']}")


if __name__ == "__main__":
    asyncio.run(main())
