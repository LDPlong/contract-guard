"""内置答疑助手测试：边界拦截、引用校验、空检索降级。

原则和审查一致——宁可不答，不编。
"""

from __future__ import annotations

import json

import pytest

from app.services import assistant
from app.services.llm.client import LLMClient
from app.services.rag.types import RetrievedChunk

CHUNK = RetrievedChunk(
    chunk_id="civil_code:五百八十五",
    content="约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。",
    score=0.9,
    article_no="第五百八十五条",
    source="民法典",
    effective_date="2021-01-01",
)


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.queries: list[str] = []

    async def search(self, query, top_k=5):
        self.queries.append(query)
        return self.chunks[:top_k]


def fake_client(payload: dict, calls: list | None = None) -> LLMClient:
    async def transport(messages, json_mode, max_tokens):
        if calls is not None:
            calls.append(messages)
        return json.dumps(payload, ensure_ascii=False), {"prompt_tokens": 10, "completion_tokens": 5}, "fake"

    return LLMClient(transport=transport)


async def collect(question: str, retriever, client) -> list[dict]:
    events = []
    async for event in assistant.stream_answer(
        question=question, retriever=retriever, client=client
    ):
        events.append(event)
    return events


def test_out_of_scope_patterns():
    assert assistant.looks_out_of_scope("我能赢吗")
    assert assistant.looks_out_of_scope("预测一下判决结果")
    assert assistant.looks_out_of_scope("帮我写一条违约金条款")
    assert not assistant.looks_out_of_scope("房东不退押金合法吗")


@pytest.mark.asyncio
async def test_refuses_without_calling_model():
    calls: list = []
    payload = {"scope_ok": True, "answer": "不该被调用", "used_chunk_ids": []}
    events = await collect(
        "我这个案子能赢吗",
        FakeRetriever([CHUNK]),
        fake_client(payload, calls),
    )
    assert calls == [], "越界提问不应该调用模型"
    assert len(events) == 1
    assert events[0]["event"] == "answer"
    assert events[0]["data"]["scope_ok"] is False
    assert events[0]["data"]["reason"] == "rule"


@pytest.mark.asyncio
async def test_refs_emitted_before_answer():
    payload = {"scope_ok": True, "answer": "违约金过高可以请求调减。", "used_chunk_ids": [CHUNK.chunk_id]}
    events = await collect("违约金太高怎么办", FakeRetriever([CHUNK]), fake_client(payload))

    assert [e["event"] for e in events] == ["refs", "answer"]
    assert events[0]["data"]["refs"][0]["chunk_id"] == CHUNK.chunk_id
    assert events[1]["data"]["answer"].startswith("违约金过高")


@pytest.mark.asyncio
async def test_unknown_chunk_id_is_dropped():
    # 模型引用了本轮没给它的条号，必须丢弃，不能出现在结果里
    payload = {
        "scope_ok": True,
        "answer": "依据合同法第九条……",
        "used_chunk_ids": ["contract_law:九", CHUNK.chunk_id],
    }
    events = await collect("押金能不退吗", FakeRetriever([CHUNK]), fake_client(payload))
    refs = events[-1]["data"]["refs"]
    assert [r["chunk_id"] for r in refs] == [CHUNK.chunk_id]


@pytest.mark.asyncio
async def test_empty_retrieval_does_not_call_model():
    calls: list = []
    payload = {"scope_ok": True, "answer": "编的答案", "used_chunk_ids": []}
    events = await collect("外星人租房要不要交税", FakeRetriever([]), fake_client(payload, calls))
    assert calls == [], "检索为空时不该让模型凭空作答"
    assert events[-1]["data"]["reason"] == "retrieve_empty"
    assert events[-1]["data"]["answer"] == assistant.NO_LAW


@pytest.mark.asyncio
async def test_question_is_truncated_and_trimmed():
    retriever = FakeRetriever([CHUNK])
    payload = {"scope_ok": True, "answer": "ok", "used_chunk_ids": []}
    long_question = "押" * 500
    await collect(long_question, retriever, fake_client(payload))
    assert len(retriever.queries[0]) == assistant.MAX_QUESTION_CHARS


@pytest.mark.asyncio
async def test_prompt_carries_chunk_ids_only_from_retrieval():
    payload = {"scope_ok": True, "answer": "ok", "used_chunk_ids": [CHUNK.chunk_id]}
    calls: list = []
    await collect("违约金", FakeRetriever([CHUNK]), fake_client(payload, calls))
    user_msg = calls[0][-1]["content"]
    assert CHUNK.chunk_id in user_msg
    assert "第五百八十五条" in user_msg


def test_expand_query_maps_colloquial_terms():
    queries = assistant.expand_query("房东不退押金合法吗")
    assert len(queries) == 2
    assert "返还租赁物" in queries[1]
    # 没有命中词条就只查一次，不做无意义的扩展
    assert assistant.expand_query("这句话什么意思") == ["这句话什么意思"]


@pytest.mark.asyncio
async def test_multi_query_retrieval_merges_and_dedupes():
    class TwoWayRetriever:
        def __init__(self):
            self.queries: list[str] = []

        async def search(self, query, top_k=5):
            self.queries.append(query)
            if len(self.queries) == 1:
                return [RetrievedChunk("a", "t1", 0.5, "第六条", "民法典")]
            return [
                RetrievedChunk("a", "t1", 0.9, "第六条", "民法典"),   # 重复命中，取高分
                RetrievedChunk("b", "t2", 0.8, "第七百三十三条", "民法典"),
            ]

    retriever = TwoWayRetriever()
    chunks = await assistant._search(retriever, "房东不退押金")
    assert len(retriever.queries) == 2
    assert [c.chunk_id for c in chunks] == ["a", "b"]
    assert chunks[0].score == 0.9
