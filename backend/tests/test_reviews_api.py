"""审查接口集成测试：SSE 事件序列 + 结果落库 + 会话隔离。

模型与检索全部注入假实现，不联网、不烧 token。
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import review_service
from app.services.llm.client import LLMClient
from app.services.rag.types import RetrievedChunk

SESSION = "review-session-001"

PAYLOAD = {
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
    "negotiation_tip": "违约金按实际损失写。",
    "confidence": 0.9,
}


class FakeRetriever:
    async def search(self, query, top_k=5):
        return [
            RetrievedChunk(
                "civil_code:五百八十五", "条文", 0.9, "第五百八十五条", "民法典", "2021-01-01"
            )
        ]


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    def client_factory():
        async def transport(messages, json_mode, max_tokens):
            return json.dumps(PAYLOAD, ensure_ascii=False), {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }, "fake-model"

        return LLMClient(transport=transport)

    monkeypatch.setattr(review_service, "llm_client_factory", client_factory)
    monkeypatch.setattr(review_service, "retriever_factory", FakeRetriever)


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def upload(client: AsyncClient, content: bytes, contract_type: str = "lease") -> str:
    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", content, "application/pdf")},
        data={"contract_type": contract_type},
        headers={"X-Session-Id": SESSION},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["document_id"]


def parse_stream(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        event, data = "", ""
        for line in block.strip().splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data += line[len("data:") :].strip()
        if event:
            events.append((event, json.loads(data) if data else {}))
    return events


@pytest.mark.asyncio
async def test_review_stream_and_persist(client, chinese_pdf_bytes):
    doc_id = await upload(client, chinese_pdf_bytes)

    async with client.stream(
        "POST",
        f"/api/v1/documents/{doc_id}/review",
        headers={"X-Session-Id": SESSION},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in resp.aiter_text()])

    events = parse_stream(body)
    kinds = [e for e, _ in events]
    assert kinds[0] == "step"
    assert kinds[-1] == "done"
    assert "progress" in kinds

    done = events[-1][1]
    assert done["review_id"]
    assert done["safety_score"] < 100
    assert done["findings"]

    # 落库校验：重新查一次
    resp = await client.get(
        f"/api/v1/reviews/{done['review_id']}", headers={"X-Session-Id": SESSION}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] in {"done", "partial"}
    assert data["safety_score"] == done["safety_score"]
    assert len(data["findings"]) == len(done["findings"])

    # 条款级结论必须映射到数据库 clauses.id（必备条款缺失类没有对应条款，跳过）
    linked = [f for f in data["findings"] if f["item_id"] != "L09"]
    assert linked and all(f["clause_id"] for f in linked)
    keys = [k for k in linked[0]["legal_basis"] if k["chunk_id"]]
    assert keys
    assert any(
        b["chunk_id"] == "civil_code:五百八十五"
        for f in linked
        for b in f["legal_basis"]
    )


@pytest.mark.asyncio
async def test_review_requires_session(client, sample_pdf_bytes):
    doc_id = await upload(client, sample_pdf_bytes)
    resp = await client.post(f"/api/v1/documents/{doc_id}/review")
    assert resp.status_code == 400
    assert resp.json()["code"] == 1004


@pytest.mark.asyncio
async def test_review_of_missing_document(client):
    resp = await client.post(
        "/api/v1/documents/not-exist/review", headers={"X-Session-Id": SESSION}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_reviews(client, sample_pdf_bytes):
    doc_id = await upload(client, sample_pdf_bytes)

    async with client.stream(
        "POST", f"/api/v1/documents/{doc_id}/review", headers={"X-Session-Id": SESSION}
    ) as resp:
        body = "".join([chunk async for chunk in resp.aiter_text()])
    assert parse_stream(body)[-1][0] == "done"

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/reviews", headers={"X-Session-Id": SESSION}
    )
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1
    assert items[0]["safety_score"] is not None
