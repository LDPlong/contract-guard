"""v1.2 补充测试：框架审阅与依据充分性闸门。"""

from __future__ import annotations

import json

import pytest

from app.core.constants import Priority
from app.services.agent.checklist import Checklist, ChecklistItem
from app.services.agent.framework import open_question_of, review_framework, stance_of
from app.services.agent.workflow import run_review
from app.services.llm.client import LLMClient
from app.services.parsing.models import Clause
from app.services.rag.types import RetrievedChunk


def clause(seq: int, text: str) -> Clause:
    return Clause(
        seq=seq,
        clause_no=f"第{seq}条",
        heading_kind="clause",
        page_no=1,
        bbox=(72.0, 100.0, 500.0, 130.0),
        text=text,
        char_start=seq * 100,
        char_end=seq * 100 + len(text),
    )


def item(**overrides) -> ChecklistItem:
    base = dict(
        id="L02",
        name="违约金比例",
        category="违约金",
        keywords=["违约金"],
        query="约定的违约金过分高于造成的损失",
        risk_rule="违约金过高",
        legal_refs=["民法典 第五百八十五条"],
        weight="high",
    )
    base.update(overrides)
    return ChecklistItem(**base)


class Retriever:
    def __init__(self, chunks):
        self.chunks = chunks

    async def search(self, query, top_k=5):
        return self.chunks[:top_k]

    def resolve_refs(self, refs):
        return []


def client(payload: dict | None = None) -> LLMClient:
    async def transport(messages, json_mode, max_tokens):
        body = payload or {
            "hit": True,
            "risk_level": "high",
            "category": "违约金",
            "title": "违约金过高",
            "reason": "约定畸高。",
            "legal_basis": [],
            "suggestion": "建议协商调整。",
            "confidence": 0.9,
        }
        return json.dumps(body, ensure_ascii=False), {"prompt_tokens": 1, "completion_tokens": 1}, "fake"

    return LLMClient(transport=transport)


CHUNK = RetrievedChunk(
    "civil_code:五百八十五", "条文", 0.9, "第五百八十五条", "民法典", "2021-01-01"
)


# ---------- 框架四问 ----------


def test_framework_detects_one_sided_obligations():
    clauses = [
        clause(1, "乙方应当按时支付租金。"),
        clause(2, "乙方须承担房屋日常维修费用。"),
        clause(3, "乙方不得擅自改变房屋用途。"),
        clause(4, "乙方应负责缴纳物业费。"),
    ]
    flags = {o["item_id"] for o in review_framework(clauses)}
    assert "F01" in flags


def test_framework_silent_on_balanced_contract():
    clauses = [
        clause(1, "甲方应当交付可正常使用的房屋。"),
        clause(2, "乙方应当按时支付租金。"),
        clause(3, "甲方须负责房屋主体结构维修。"),
        clause(4, "乙方不得擅自改变房屋用途。"),
    ]
    flags = {o["item_id"] for o in review_framework(clauses)}
    assert "F01" not in flags


def test_framework_detects_unilateral_exit():
    clauses = [
        clause(1, "甲方有权随时解除合同，收回房屋。"),
        clause(2, "乙方不得提前解除，租金一律不退。"),
    ]
    flags = {o["item_id"] for o in review_framework(clauses)}
    assert "F02" in flags


def test_framework_detects_false_premise():
    clauses = [
        clause(1, "视为乙方已充分知悉房屋现状并验收。"),
        clause(2, "乙方无条件放弃任何抗辩，不得以任何理由拒付租金。"),
    ]
    flags = {o["item_id"] for o in review_framework(clauses)}
    assert "F04" in flags


def test_stance_and_open_question_are_type_specific():
    assert "承租方" in stance_of("lease")
    assert "劳动者" in stance_of("labor")
    assert "抵押" in open_question_of("lease")
    assert open_question_of("unknown")


# ---------- 依据充分性闸门 ----------


@pytest.mark.asyncio
async def test_zero_legal_basis_skips_model_and_marks_review():
    def never_called(*args, **kwargs):
        raise AssertionError("零法条命中时不应调用模型")

    llm = LLMClient(transport=never_called)
    board = Checklist(contract_type="lease", version="test", items=[item()])
    done = None
    async for event in run_review(
        clauses=[clause(1, "乙方逾期支付租金的，应当支付违约金。")],
        full_text="乙方逾期支付租金的，应当支付违约金。",
        contract_type="lease",
        checklist=board,
        retriever=Retriever([]),
        client=llm,
    ):
        if event["event"] == "done":
            done = event["data"]

    assert done["needs_review"] == 1
    assert done["safety_score"] == 100
    assert "依据不足" in done["findings"][0]["title"]
    assert done["findings"][0]["risk_level"] == "none"


@pytest.mark.asyncio
async def test_one_pinned_chunk_allows_judgement():
    board = Checklist(contract_type="lease", version="test", items=[item()])
    done = None
    async for event in run_review(
        clauses=[clause(1, "乙方逾期支付租金的，应当支付违约金。")],
        full_text="乙方逾期支付租金的，应当支付违约金。",
        contract_type="lease",
        checklist=board,
        retriever=Retriever([CHUNK]),
        client=client(),
    ):
        if event["event"] == "done":
            done = event["data"]

    finding = next(f for f in done["findings"] if f["item_id"] == "L02")
    assert finding["risk_level"] == "high"
    assert finding["priority"] == Priority.MUST
    assert finding["impact"]
    assert done["stance"] and done["open_question"]


@pytest.mark.asyncio
async def test_framework_observation_is_low_and_keeps_bbox_anchor():
    clauses = [
        clause(1, "乙方应当按时支付租金。"),
        clause(2, "乙方须承担房屋日常维修费用。"),
        clause(3, "乙方不得擅自改变房屋用途。"),
        clause(4, "乙方应负责缴纳物业费。"),
    ]
    board = Checklist(contract_type="lease", version="test", items=[item()])
    done = None
    async for event in run_review(
        clauses=clauses,
        full_text="\n".join(c.text for c in clauses),
        contract_type="lease",
        checklist=board,
        retriever=Retriever([CHUNK]),
        client=client(),
    ):
        if event["event"] == "done":
            done = event["data"]

    framework = next(f for f in done["findings"] if f["item_id"] == "F01")
    assert framework["risk_level"] == "low"
    assert framework["clause_seq"] == 1
    assert framework["clause_no"] == "第1条"
    assert framework["priority"] == Priority.NEGOTIABLE
    assert any(flag["key"] == "F01" for flag in done["framework_flags"])
