"""文档服务：上传落库、异步解析、查询与删除。

解析流程遵循文档 8.1：
- 请求内同步等待，超过 PARSE_TIMEOUT_SEC 返回 2003（status=parsing）
- 超时后任务**继续在后台跑**（asyncio.shield 保证不被取消），前端轮询 GET 拿结果
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.constants import (
    STALE_PARSING_MINUTES,
    SUPPORTED_CONTRACT_TYPES,
    ContractType,
    ErrorCode,
)
from app.core.errors import BizError, ParseFailed
from app.core.logging import get_logger
from app.models.base import SessionLocal
from app.models.document import Clause, Document
from app.services.parsing import detect, parse_pdf, split_clauses
from app.services.parsing.vision_parser import parse_image
from app.services.storage import SavedFile, remove_saved_file

log = get_logger(__name__)


@dataclass
class ProcessResult:
    status: str
    contract_type: str
    type_source: str
    page_count: int
    clause_count: int
    error: str | None = None


async def create_document(
    session: AsyncSession,
    *,
    saved: SavedFile,
    filename: str,
    session_id: str,
    user_contract_type: str | None = None,
) -> tuple[Document, bool]:
    """落库并返回 (文档, 是否新建)。同 session 内 sha256 相同视为重复上传，直接复用。"""
    existing = await session.scalar(
        select(Document)
        .where(Document.session_id == session_id, Document.sha256 == saved.sha256)
        .where(Document.status != "failed")
        .order_by(Document.created_at.desc())
    )
    if existing is not None:
        remove_saved_file(saved.file_path)
        log.info("duplicate upload reused", extra={"document_id": existing.id})
        return existing, False

    user_choice = user_contract_type if user_contract_type in SUPPORTED_CONTRACT_TYPES else None
    doc = Document(
        session_id=session_id,
        filename=filename[:255],
        stored_name=saved.stored_name,
        file_path=str(saved.file_path),
        mime_type=saved.mime_type,
        size_bytes=saved.size_bytes,
        sha256=saved.sha256,
        contract_type=user_choice,
        type_source="user" if user_choice else None,
        status="uploaded",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc, True


async def process_document(document_id: str) -> ProcessResult:
    """解析 + 切分 + 类型识别 + 落条款。使用独立 session，避免请求结束即失效。"""
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            return ProcessResult("failed", ContractType.UNKNOWN, "unknown", 0, 0, "文档不存在")

        doc.status = "parsing"
        await session.commit()

        is_image = (doc.mime_type or "").startswith("image/")

        if is_image:
            # 图片合同：多模态模型直接读图，没有坐标，只能做条款级定位
            try:
                vision = await parse_image(doc.file_path)
            except ValueError as exc:
                doc.status = "failed"
                doc.error_msg = f"图片识别失败：{exc}"
                await session.commit()
                log.warning("vision parse failed", extra={"document_id": document_id})
                return ProcessResult(
                    "failed", ContractType.UNKNOWN, "unknown", 0, 0, doc.error_msg
                )
            clauses = vision.clauses
            full_text = vision.full_text
            page_count = 1
            pages_payload = [{"page_no": 1, "width": 0, "height": 0}]
            vision_guess = vision.contract_type
        else:
            try:
                parsed = await asyncio.to_thread(parse_pdf, doc.file_path)
            except ParseFailed as exc:
                doc.status = "failed"
                doc.error_msg = str(exc)
                await session.commit()
                log.warning("parse failed", extra={"document_id": document_id})
                return ProcessResult("failed", ContractType.UNKNOWN, "unknown", 0, 0, str(exc))
            clauses = split_clauses(parsed)
            full_text = parsed.full_text
            page_count = parsed.page_count
            pages_payload = [
                {"page_no": p.page_no, "width": p.width, "height": p.height}
                for p in parsed.pages
            ]
            vision_guess = None

        user_choice = doc.contract_type if doc.type_source == "user" else None
        detection = detect(full_text, user_choice=user_choice)
        if not detection.confident and vision_guess in SUPPORTED_CONTRACT_TYPES:
            detection.contract_type = vision_guess
            detection.source = "llm"

        doc.contract_type = detection.contract_type
        doc.type_source = detection.source
        doc.page_count = page_count
        doc.pages_json = json.dumps(pages_payload, ensure_ascii=False)

        for item in clauses:
            session.add(
                Clause(
                    document_id=doc.id,
                    seq=item.seq,
                    clause_no=item.clause_no,
                    page_no=item.page_no,
                    bbox_json=json.dumps(item.bbox) if item.bbox else None,
                    text=item.text,
                    char_start=item.char_start,
                    char_end=item.char_end,
                )
            )

        doc.status = "parsed"
        doc.error_msg = None
        await session.commit()

        return ProcessResult(
            status="parsed",
            contract_type=detection.contract_type,
            type_source=detection.source,
            page_count=page_count,
            clause_count=len(clauses),
        )


async def get_document(session: AsyncSession, document_id: str, session_id: str) -> Document:
    doc = await session.scalar(
        select(Document)
        .options(selectinload(Document.clauses))
        .where(Document.id == document_id, Document.session_id == session_id)
    )
    if doc is None:
        raise BizError(ErrorCode.NOT_FOUND, "文档不存在或不属于当前会话")
    return doc


async def get_file_path(
    session: AsyncSession, document_id: str, session_id: str
) -> tuple[Path, str, str]:
    """返回 (磁盘路径, 原始文件名)。只按 id 查库取路径，绝不拼接用户输入。"""
    doc = await get_document(session, document_id, session_id)
    path = Path(doc.file_path)
    if not path.is_file():
        raise BizError(ErrorCode.NOT_FOUND, "原始文件已删除")
    return path, doc.filename, doc.mime_type or "application/pdf"


async def delete_document(session: AsyncSession, document_id: str, session_id: str) -> bool:
    doc = await session.scalar(
        select(Document).where(Document.id == document_id, Document.session_id == session_id)
    )
    if doc is None:
        return False
    path = doc.file_path
    await session.delete(doc)
    await session.commit()
    remove_saved_file(path)
    return True


def parse_timeout() -> int:
    return get_settings().parse_timeout_sec


async def repair_stale_parsing(minutes: int = STALE_PARSING_MINUTES) -> int:
    """启动自检（文档 3.4）：把服务重启前残留的 parsing 记录标记为 failed。

    单 worker + 进程内任务，重启即丢任务，状态必须回收，否则前端会一直轮询。
    """
    cutoff = datetime.now() - timedelta(minutes=minutes)
    async with SessionLocal() as session:
        result = await session.execute(
            update(Document)
            .where(Document.status == "parsing", Document.created_at < cutoff)
            .values(status="failed", error_msg="服务重启，解析中断")
        )
        await session.commit()
        count = result.rowcount or 0
    if count:
        log.warning("repaired %s stale parsing documents", count)
    return count
