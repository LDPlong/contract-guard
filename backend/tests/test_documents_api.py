"""文档接口集成测试（8.1 / 8.2 / 8.3 / 8.7）。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SESSION = "test-session-001"
OTHER_SESSION = "test-session-002"


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def upload(
    client: AsyncClient,
    content: bytes,
    *,
    session: str = SESSION,
    contract_type: str | None = None,
    filename: str = "contract.pdf",
    mime: str = "application/pdf",
):
    files = {"file": (filename, content, mime)}
    data = {"contract_type": contract_type} if contract_type else None
    return await client.post(
        "/api/v1/documents", files=files, data=data, headers={"X-Session-Id": session}
    )


@pytest.mark.asyncio
async def test_upload_returns_parsed_document(client, sample_pdf_bytes):
    resp = await upload(client, sample_pdf_bytes, contract_type="lease")
    assert resp.status_code == 200

    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["status"] == "parsed"
    assert data["page_count"] == 1
    assert data["clause_count"] >= 1
    assert data["contract_type"] == "lease"
    assert data["type_source"] == "user"
    assert resp.headers["X-Session-Id"] == SESSION


@pytest.mark.asyncio
async def test_get_detail_returns_clauses_with_bbox(client, sample_pdf_bytes):
    doc_id = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]

    resp = await client.get(f"/api/v1/documents/{doc_id}", headers={"X-Session-Id": SESSION})
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["pages"][0]["width"] == pytest.approx(595, abs=1)
    assert len(data["clauses"]) >= 1

    clause = data["clauses"][0]
    assert clause["seq"] == 1
    assert isinstance(clause["bbox"], list) and len(clause["bbox"]) == 4
    x0, y0, x1, y1 = clause["bbox"]
    assert x0 < x1 and y0 < y1


@pytest.mark.asyncio
async def test_get_original_file(client, sample_pdf_bytes):
    doc_id = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]

    resp = await client.get(f"/api/v1/documents/{doc_id}/file", headers={"X-Session-Id": SESSION})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_reject_fake_pdf_by_magic_number(client):
    resp = await upload(client, b"this is not a pdf at all", filename="fake.pdf")
    assert resp.status_code == 415
    assert resp.json()["code"] == 1002


@pytest.mark.asyncio
async def test_duplicate_upload_reuses_document(client, sample_pdf_bytes):
    first = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]
    second = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]
    assert first == second


@pytest.mark.asyncio
async def test_session_isolation(client, sample_pdf_bytes):
    doc_id = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}", headers={"X-Session-Id": OTHER_SESSION}
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 1005


@pytest.mark.asyncio
async def test_missing_session_header_is_rejected(client, sample_pdf_bytes):
    doc_id = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]

    resp = await client.get(f"/api/v1/documents/{doc_id}")
    assert resp.status_code == 400
    assert resp.json()["code"] == 1004


@pytest.mark.asyncio
async def test_status_endpoint(client, sample_pdf_bytes):
    doc_id = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/status", headers={"X-Session-Id": SESSION}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "parsed"
    assert data["clause_count"] >= 1
    assert data["error_msg"] is None


@pytest.mark.asyncio
async def test_delete_then_404(client, sample_pdf_bytes):
    doc_id = (await upload(client, sample_pdf_bytes)).json()["data"]["document_id"]

    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers={"X-Session-Id": SESSION})
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True

    resp = await client.get(f"/api/v1/documents/{doc_id}", headers={"X-Session-Id": SESSION})
    assert resp.status_code == 404
