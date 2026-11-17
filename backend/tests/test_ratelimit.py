"""限流测试（M7）。

两件事必须锁住：
1. 超限返回统一信封的 4290，而不是 500 或裸 429；
2. 探活接口不能被限流——否则监控会把服务判死。
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.ratelimit import DailyQuota, RateLimiter, client_ip, is_heavy, quota_bucket
from app.main import app, settings


SESSION = "test-ratelimit"

@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------- 计数器本身 ----------


def test_limiter_allows_within_limit():
    limiter = RateLimiter()
    for _ in range(3):
        allowed, remaining, _ = limiter.hit("k", limit=3, now=1000.0)
        assert allowed
    assert remaining == 0


def test_limiter_blocks_over_limit():
    limiter = RateLimiter()
    for _ in range(2):
        limiter.hit("k", limit=2, now=1000.0)
    allowed, remaining, retry_after = limiter.hit("k", limit=2, now=1000.0)
    assert not allowed
    assert remaining == 0
    assert retry_after >= 1


def test_limiter_window_slides():
    limiter = RateLimiter(window=60.0)
    limiter.hit("k", limit=1, now=1000.0)
    assert not limiter.hit("k", limit=1, now=1030.0)[0]
    # 第一秒的那次已经滑出窗口
    assert limiter.hit("k", limit=1, now=1061.0)[0]


def test_limiter_keys_are_isolated():
    limiter = RateLimiter()
    limiter.hit("a", limit=1, now=1000.0)
    assert limiter.hit("b", limit=1, now=1000.0)[0]


def test_limiter_zero_limit_means_unlimited():
    limiter = RateLimiter()
    for _ in range(5):
        assert limiter.hit("k", limit=0, now=1000.0)[0]


def test_is_heavy_matches_upload_and_review():
    from starlette.requests import Request

    def make(method: str, path: str) -> Request:
        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
        }
        return Request(scope)

    assert is_heavy(make("POST", "/api/v1/documents"))
    assert is_heavy(make("POST", "/api/v1/documents/abc/review"))
    assert is_heavy(make("POST", "/api/v1/assistant/ask"))
    assert not is_heavy(make("GET", "/api/v1/documents"))
    assert not is_heavy(make("GET", "/api/v1/knowledge/articles"))


def test_client_ip_prefers_forwarded_header():
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")],
        "client": ("127.0.0.1", 1234),
        "query_string": b"",
    }
    assert client_ip(Request(scope), trust_proxy=True) == "1.2.3.4"


def test_client_ip_ignores_forwarded_header_by_default():
    """公网 8000 直连部署：XFF 由客户端伪造，默认必须忽略，否则限流形同虚设。"""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"1.2.3.4")],
        "client": ("127.0.0.1", 1234),
        "query_string": b"",
    }
    assert client_ip(Request(scope)) == "127.0.0.1"


# ---------- 接口层 ----------


@pytest.mark.asyncio
async def test_heavy_bucket_returns_429_envelope(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_heavy_per_minute", 1)

    # 空 body 会被参数校验挡下（项目把 422 统一成 400），但这次请求已经计过数
    first = await client.post("/api/v1/documents")
    assert first.status_code == 400

    second = await client.post("/api/v1/documents")
    assert second.status_code == 429
    body = second.json()
    assert body["code"] == 4290
    assert "频繁" in body["message"] and "秒后" in body["message"]
    assert second.headers["Retry-After"]


@pytest.mark.asyncio
async def test_health_is_not_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_heavy_per_minute", 1)

    for _ in range(5):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_forwarded_ips_only_separate_when_trusted(client, monkeypatch):
    """默认不信任 XFF：伪造头拿不到独立桶；置于可信反代后开启才生效。"""
    monkeypatch.setattr(settings, "rate_limit_heavy_per_minute", 1)

    # 默认：伪造 XFF 无效，同源第二个请求被限
    await client.post("/api/v1/documents", headers={"X-Forwarded-For": "1.1.1.1"})
    blocked = await client.post("/api/v1/documents", headers={"X-Forwarded-For": "1.1.1.1"})
    assert blocked.status_code == 429

    # 显式信任代理后：不同 XFF 有独立桶
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    from app.core.ratelimit import limiter

    limiter.reset()
    await client.post("/api/v1/documents", headers={"X-Forwarded-For": "1.1.1.1"})
    ok_first = await client.post("/api/v1/documents", headers={"X-Forwarded-For": "1.1.1.1"})
    assert ok_first.status_code == 429
    other = await client.post("/api/v1/documents", headers={"X-Forwarded-For": "2.2.2.2"})
    assert other.status_code == 400


@pytest.mark.asyncio
async def test_limiter_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_heavy_per_minute", 1)

    for _ in range(3):
        resp = await client.post("/api/v1/documents")
        assert resp.status_code == 400


# ---------- 每日配额 ----------


def test_quota_bucket_matches_model_consuming_paths():
    from starlette.requests import Request

    def make(method: str, path: str) -> Request:
        scope = {"type": "http", "method": method, "path": path, "headers": [], "query_string": b""}
        return Request(scope)

    assert quota_bucket("/api/v1/documents/x/review", "POST") == "review"
    assert quota_bucket("/api/v1/assistant/ask", "POST") == "assistant"
    # 上传与解析不调模型，不占配额
    assert quota_bucket("/api/v1/documents", "POST") is None
    assert quota_bucket("/api/v1/documents/x/review", "GET") is None
    assert quota_bucket("/api/v1/knowledge/articles", "GET") is None


def test_daily_quota_resets_by_day():
    quota = DailyQuota()
    assert quota.hit("review", limit=1) == (True, 1)
    assert quota.hit("review", limit=1) == (False, 1)


@pytest.mark.asyncio
async def test_review_daily_quota_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "review_daily_limit", 1)
    from app.core.ratelimit import daily_quota

    daily_quota.reset()

    # 不存在的文档：路由抛 404，但配额在中间件计数——挡在模型调用之前
    first = await client.post(
        "/api/v1/documents/does-not-exist/review", headers={"X-Session-Id": SESSION}
    )
    assert first.status_code == 404

    second = await client.post(
        "/api/v1/documents/does-not-exist/review", headers={"X-Session-Id": SESSION}
    )
    assert second.status_code == 429
    body = second.json()
    assert body["code"] == 4290
    assert "上限" in body["message"]
    assert body["data"]["bucket"] == "review"
