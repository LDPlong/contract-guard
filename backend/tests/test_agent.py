"""Agent 层测试：预筛、评分、工作流与防幻觉约束。"""

from __future__ import annotations

import json

import pytest

from app.services.agent.checklist import Checklist, ChecklistItem
from app.services.agent.gating import Gate
from app.services.agent.tools import calc_safety_score, check_missing
from app.services.agent.workflow import run_review
from app.services.llm.client import LLMClient
from app.services.parsing.models import Clause
from app.services.rag.types import RetrievedChunk


def make_clause(seq: int, text: str, clause_no: str | None = None, page: int = 1) -> Clause:
    return Clause(
        seq=seq,
        clause_no=clause_no,
        heading_kind="clause" if clause_no else None,
        page_no=page,
        bbox=(72.0, 100.0, 500.0, 130.0),
        text=text,
        char_start=seq * 100,
        char_end=seq * 100 + len(text),
    )


def make_item(**overrides) -> ChecklistItem:
    base = dict(
        id="T01",
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


# ---------- 评分 ----------


def test_score_deduction_and_clamp():
    assert calc_safety_score([]) == 100
    assert calc_safety_score(["high"]) == 88
    assert calc_safety_score(["high", "high", "medium"]) == 71
    assert calc_safety_score(["low"] * 60) == 0  # clamp 到 0


def test_missing_items_deduct():
    assert calc_safety_score([], missing_items=3) == 76


def test_check_missing():
    text = "本合同约定租金每月三千元。"
    assert check_missing(text, ["租金", "租赁期限"]) == ["租赁期限"]


def test_check_missing_accepts_synonym_alternatives():
    # 房屋坐落于 XX 路 = 写清了地址；不能因为没出现"地址"两个字就判缺项
    text = "第一条 房屋坐落于成都市武侯区科华北路 66 号。租赁期限 12 个月，月租金 3200 元。"
    assert check_missing(text, ["租赁期限", "租金", "地址|坐落"]) == []
    # 没写门牌就是没写，别被"位于"蒙过去
    vague = "房屋位于某小区，具体门牌以带看为准。租金 2600 元。"
    assert check_missing(vague, ["租金", "地址|坐落"]) == ["地址"]


# ---------- 预筛 ----------


def test_gate_prefers_keyword_hits():
    clauses = [
        make_clause(1, "甲方应在乙方入住前交付房屋。", "第一条"),
        make_clause(2, "乙方逾期支付租金的，应按约定支付违约金。", "第二条"),
        make_clause(3, "本合同一式两份。", "第三条"),
    ]
    gate = Gate(clauses)
    candidates = gate.candidates(make_item())

    assert candidates
    assert candidates[0].clause.clause_no == "第二条"
    assert "违约金" in candidates[0].keyword_hits


def test_gate_returns_empty_when_nothing_matches():
    gate = Gate([make_clause(1, "本合同一式两份，双方签字生效。", "第一条")])
    assert gate.candidates(make_item(keywords=["量子"], query="量子纠缠")) == []


def test_gate_respects_top_k():
    clauses = [make_clause(i, f"违约金相关约定第{i}条。", f"第{i}条") for i in range(1, 9)]
    assert len(Gate(clauses, top_k=3).candidates(make_item())) == 3


# ---------- 工作流 ----------


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.queries: list[str] = []

    async def search(self, query, top_k=5):
        self.queries.append(query)
        return self.chunks[:top_k]

    def resolve_refs(self, refs):
        """参考法条通道：测试里统一按"检索到什么用什么"处理。"""
        return []


def fake_client(payload: dict) -> LLMClient:
    async def transport(messages, json_mode, max_tokens):
        return json.dumps(payload, ensure_ascii=False), {"prompt_tokens": 10, "completion_tokens": 5}, "fake"

    return LLMClient(transport=transport)


CLAUSE_OK = [make_clause(1, "乙方逾期支付租金的，应按约定支付违约金。", "第二条")]


@pytest.mark.asyncio
async def test_workflow_emits_events_and_scores():
    payload = {
        "hit": True,
        "risk_level": "high",
        "category": "违约金",
        "title": "违约金过高",
        "reason": "第二条约定违约金畸高。",
        "legal_basis": [
            {
                "source": "民法典",
                "article": "第五百八十五条",
                "quote": "约定的违约金过分高于造成的损失的，可以请求适当减少。",
                "chunk_id": "civil_code:五百八十五",
            }
        ],
        "suggestion": "建议将违约金调整为与实际损失相当。",
        "negotiation_tip": "违约金按实际损失写，双方都清楚。",
        "confidence": 0.9,
    }
    retriever = FakeRetriever(
        [RetrievedChunk("civil_code:五百八十五", "条文", 0.9, "第五百八十五条", "民法典", "2021-01-01")]
    )
    board = Checklist(contract_type="lease", version="test", items=[make_item()])

    events = []
    async for event in run_review(
        clauses=CLAUSE_OK,
        full_text=CLAUSE_OK[0].text,
        contract_type="lease",
        checklist=board,
        retriever=retriever,
        client=fake_client(payload),
    ):
        events.append(event)

    kinds = [e["event"] for e in events]
    assert kinds[0] == "step" and kinds[-1] == "done"
    assert "progress" in kinds

    done = events[-1]["data"]
    assert done["safety_score"] == 88
    assert len(done["findings"]) == 1
    finding = done["findings"][0]
    assert finding["clause_no"] == "第二条"
    assert finding["legal_basis"][0]["chunk_id"] == "civil_code:五百八十五"


@pytest.mark.asyncio
async def test_workflow_drops_hallucinated_legal_basis():
    payload = {
        "hit": True,
        "risk_level": "high",
        "title": "编造依据",
        "reason": "测试。",
        "legal_basis": [
            {"source": "民法典", "article": "第九百九十九条", "quote": "编的", "chunk_id": "made-up:999"}
        ],
        "suggestion": "建议。",
        "confidence": 0.95,
    }
    retriever = FakeRetriever(
        [RetrievedChunk("civil_code:五百八十五", "条文", 0.9, "第五百八十五条", "民法典")]
    )
    board = Checklist(contract_type="lease", version="test", items=[make_item()])

    done = None
    async for event in run_review(
        clauses=CLAUSE_OK,
        full_text=CLAUSE_OK[0].text,
        contract_type="lease",
        checklist=board,
        retriever=retriever,
        client=fake_client(payload),
    ):
        if event["event"] == "done":
            done = event["data"]

    finding = done["findings"][0]
    assert finding["legal_basis"] == []
    # 无依据时置信度必须被压到 0.5 以下
    assert finding["confidence"] <= 0.5


@pytest.mark.asyncio
async def test_workflow_marks_review_needed_on_bad_json():
    async def transport(messages, json_mode, max_tokens):
        return "这不是 JSON", {"prompt_tokens": 1, "completion_tokens": 1}, "fake"

    board = Checklist(contract_type="lease", version="test", items=[make_item()])
    done = None
    async for event in run_review(
        clauses=CLAUSE_OK,
        full_text=CLAUSE_OK[0].text,
        contract_type="lease",
        checklist=board,
        retriever=FakeRetriever([]),
        client=LLMClient(transport=transport),
    ):
        if event["event"] == "done":
            done = event["data"]

    assert done["needs_review"] == 1
    # 兜底项以"待复核"卡片保留（对应 F9），但风险等级为 none，不扣分
    assert len(done["findings"]) == 1
    assert done["findings"][0]["risk_level"] == "none"
    assert done["findings"][0]["needs_review"] is True
    assert done["safety_score"] == 100


@pytest.mark.asyncio
async def test_missing_item_detected_without_llm():
    async def transport(messages, json_mode, max_tokens):
        raise AssertionError("missing_check 模式不应调用模型")

    item = make_item(
        id="L09",
        name="必备条款缺失",
        category="必备条款",
        keywords=["租赁期限"],
        mode="missing_check",
        required_terms=["租赁期限", "租金"],
        weight="high",
    )
    board = Checklist(contract_type="lease", version="test", items=[item])
    done = None
    async for event in run_review(
        clauses=CLAUSE_OK,
        full_text=CLAUSE_OK[0].text,
        contract_type="lease",
        checklist=board,
        retriever=FakeRetriever([]),
        client=LLMClient(transport=transport),
    ):
        if event["event"] == "done":
            done = event["data"]

    assert done["findings"][0]["category"] == "必备条款"
    assert done["safety_score"] < 100
