"""数据库引擎与会话。

运行约束（文档 3.4）：
1. SQLite 必须开 WAL，否则 SSE 长连接期间写 findings 会 database is locked
2. SQLite 默认外键关闭，必须显式 `PRAGMA foreign_keys=ON`，否则 ON DELETE CASCADE 不生效
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import BACKEND_DIR, get_settings

_SQLITE_PREFIX = "sqlite+aiosqlite:///"


def _resolve_db_url(url: str) -> str:
    """把相对 SQLite 路径锚定到 backend/，避免受启动时 CWD 影响。"""
    if not url.startswith(_SQLITE_PREFIX):
        return url
    raw = url[len(_SQLITE_PREFIX) :]
    if raw == ":memory:" or raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        return url
    path = (BACKEND_DIR / raw).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return _SQLITE_PREFIX + path.as_posix()


class Base(DeclarativeBase):
    pass


_settings = get_settings()
DB_URL = _resolve_db_url(_settings.db_url)

engine = create_async_engine(DB_URL, echo=False, pool_pre_ping=True)


if DB_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """开发/演示环境建表。生产应走迁移脚本。"""
    import app.models  # noqa: F401  确保所有模型已注册

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def sqlite_file_path() -> Path | None:
    if not DB_URL.startswith(_SQLITE_PREFIX):
        return None
    return Path(DB_URL[len(_SQLITE_PREFIX) :])
