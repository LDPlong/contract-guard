"""健康检查。

约定（文档 8.10）：
- 本接口**不使用** {code,message,data} 包装，直接返回状态对象
- `llm` 只检查配置完整性，不发起真实调用（避免健康检查烧钱）
- `vector` 检查索引文件是否存在且维度可读
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.base import engine

router = APIRouter(tags=["health"])
log = get_logger(__name__)


async def _check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        log.warning("health: db check failed", exc_info=True)
        return False


def _check_index() -> tuple[bool, int | None]:
    meta_file = get_settings().index_path / "meta.json"
    if not meta_file.is_file():
        return False, None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    return bool(meta.get("chunk_count")), meta.get("dim")


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    db_ok = await _check_db()
    index_built, dim = _check_index()
    body = {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "vector": index_built,
        "index_built": index_built,
        "embedding_dim": dim,
        "llm": settings.llm_configured,
        "ocr_enabled": settings.ocr_enabled,
        "demo_mode": settings.demo_mode,
        "env": settings.app_env,
    }
    if not db_ok:
        body["status"] = "degraded"
    return body
