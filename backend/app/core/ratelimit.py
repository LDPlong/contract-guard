"""请求限流（M7 补齐）。

单进程内存计数，按「客户端 IP + 配额档位」做 60 秒滑动窗口。
不引 Redis：部署形态就是一个 uvicorn worker，跨进程限流本来也没意义。

两个档位：
- heavy：上传、发起审查、答疑。这三类是模型调用与磁盘写入的入口，最贵
- default：其余读写接口

配套约束：反向代理后 request.client.host 恒为 127.0.0.1，
必须优先取 X-Forwarded-For，否则全站共用一个桶。
"""

from __future__ import annotations

import time
from collections import deque

from fastapi import Request

WINDOW_SEC = 60.0
# 超过这个数量就清一轮全表，避免长期运行后 key 无限增长
SWEEP_THRESHOLD = 4096
# 这些路径不参与限流：探活、文档、静态资源
EXEMPT_PREFIXES = (
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/assets/",
)
HEAVY_SUFFIXES = ("/review",)
HEAVY_EXACT = ("/api/v1/documents", "/api/v1/assistant/ask")


def client_ip(request: Request) -> str:
    """反代场景下取真实来源；没有代理头时用连接地址。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = request.headers.get("X-Real-IP")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def is_heavy(request: Request) -> bool:
    path = request.url.path
    if request.method == "POST" and path.rstrip("/") in {p.rstrip("/") for p in HEAVY_EXACT}:
        return True
    return path.endswith(HEAVY_SUFFIXES)


def is_exempt(path: str) -> bool:
    return path.startswith(EXEMPT_PREFIXES)


class RateLimiter:
    """滑动窗口计数器。窗口内的时间戳用 deque 存，过期即弹。"""

    def __init__(self, window: float = WINDOW_SEC) -> None:
        self.window = window
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, limit: int, now: float | None = None) -> tuple[bool, int, int]:
        """记一次访问。

        Returns:
            (是否放行, 剩余配额, 建议等待秒数)
        """
        if limit <= 0:
            return True, 0, 0

        ts = time.monotonic() if now is None else now
        bucket = self._hits.get(key)
        if bucket is None:
            bucket = deque()
            self._hits[key] = bucket

        cutoff = ts - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(self.window - (ts - bucket[0])) + 1)
            return False, 0, retry_after

        bucket.append(ts)
        if len(self._hits) > SWEEP_THRESHOLD:
            self._sweep(cutoff)
        return True, limit - len(bucket), 0

    def _sweep(self, cutoff: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            self._hits.pop(key, None)

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter()
