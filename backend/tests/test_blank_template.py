"""空白模板识别（文档 6.2、10.2）。

空白模板上"未约定/未载明"的结论不成立——那只是还没填。这里锁定两条底线：
1. 空白模板只降中风险，高风险不动；
2. 已填写的合同不受影响。
"""

from __future__ import annotations

from pathlib import Path

from app.services.agent import workflow
from app.services.agent.tools import count_fill_blanks, is_blank_template
from app.services.parsing import parse_pdf, split_clauses

SAMPLES = Path(__file__).parents[1] / "tests" / "fixtures" / "samples"


def _clauses(name: str):
    return split_clauses(parse_pdf(SAMPLES / name))


def test_blank_template_detected_on_official_form() -> None:
    # 广东省住建厅示范文本：大量待填金额、勾选框
    clauses = _clauses("lease_gd.pdf")
    assert count_fill_blanks(clauses) > 20
    assert is_blank_template(clauses) is True


def test_filled_contract_is_not_blank_template() -> None:
    # 已填写的合同（有具体金额、期限、当事人），不应被判为模板
    clauses = _clauses("eval/lease_city_01.pdf")
    assert is_blank_template(clauses) is False


def test_empty_input_is_not_blank_template() -> None:
    assert is_blank_template([]) is False


def test_soften_only_touches_medium() -> None:
    drafts = [
        workflow.FindingDraft(
            item_id="L01",
            category="押金",
            risk_level="medium",
            title="中风险项",
            reason="未约定退还时限",
            suggestion="补充",
        ),
        workflow.FindingDraft(
            item_id="L02",
            category="违约金",
            risk_level="high",
            title="高风险项",
            reason="概不退款",
            suggestion="删除",
        ),
    ]
    softened = workflow._soften_blank_template(drafts)
    assert softened[0].risk_level == "low"
    assert softened[0].needs_review is True
    assert "空白待填项" in softened[0].reason
    assert softened[1].risk_level == "high"
    assert softened[1].needs_review is False
    assert softened[1].reason == "概不退款"
