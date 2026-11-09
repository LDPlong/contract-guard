import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_200_and_checks_db():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    # 健康接口不走统一包装（文档 8.10）
    assert "code" not in body
    assert body["db"] is True
    assert body["status"] in {"ok", "degraded"}
    # 未建索引时应为 False，不报错
    assert isinstance(body["vector"], bool)


@pytest.mark.asyncio
async def test_root_is_wrapped():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "ContractGuard"


@pytest.mark.asyncio
async def test_404_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/not-exist")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_request_id_header_echoed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health", headers={"X-Request-Id": "abc123"})

    assert resp.headers["X-Request-Id"] == "abc123"
