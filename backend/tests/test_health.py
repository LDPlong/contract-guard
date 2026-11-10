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
async def test_root_serves_spa_or_envelope():
    """有前端产物时根路径返回 index.html（单进程部署）；没有时返回 JSON 说明。

    两种形态都合法，取决于 frontend/dist 是否存在，所以这里按内容类型分支断言。
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    content_type = resp.headers["content-type"]
    if content_type.startswith("application/json"):
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["name"] == "ContractGuard"
    else:
        assert "text/html" in content_type


@pytest.mark.asyncio
async def test_api_404_is_not_swallowed_by_spa():
    """SPA 回退不能吃掉接口前缀：写错的接口必须返回 404，而不是一页 HTML。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/definitely-not-exist")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


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
