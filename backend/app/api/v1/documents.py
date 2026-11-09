"""文档接口（文档 8.1 / 8.2 / 8.3 / 8.7）。

路由层只做参数校验与编排，业务在 services/document_service.py。
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ErrorCode
from app.core.errors import BadRequest, BizError, ParseFailed, ok
from app.core.logging import get_logger
from app.models.base import get_session
from app.models.document import Clause
from app.schemas.document import DeleteOut, UploadOut, to_detail
from app.services import document_service
from app.services.storage import save_upload

router = APIRouter(prefix="/documents", tags=["documents"])
log = get_logger(__name__)

SESSION_HEADER = "X-Session-Id"


def _session_from(request: Request, header_value: str | None) -> str:
    raw = header_value or request.headers.get(SESSION_HEADER) or uuid.uuid4().hex
    return raw[:64]


def _require_session(header_value: str | None) -> str:
    if not header_value:
        raise BizError(ErrorCode.SESSION_INVALID, "缺少 X-Session-Id")
    return header_value[:64]


async def _count_clauses(session: AsyncSession, document_id: str) -> int:
    total = await session.scalar(
        select(func.count()).select_from(Clause).where(Clause.document_id == document_id)
    )
    return int(total or 0)


@router.post("", summary="上传合同（8.1）")
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    contract_type: str | None = Form(default=None),
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    session_id = _session_from(request, x_session_id)
    response.headers[SESSION_HEADER] = session_id

    if not file.filename:
        raise BadRequest("缺少文件名")

    saved = await save_upload(file)
    doc, created = await document_service.create_document(
        session,
        saved=saved,
        filename=file.filename,
        session_id=session_id,
        user_contract_type=contract_type,
    )

    if not created:
        payload = UploadOut(
            document_id=doc.id,
            status=doc.status,
            contract_type=doc.contract_type or "unknown",
            type_source=doc.type_source or "unknown",
            page_count=doc.page_count,
            clause_count=await _count_clauses(session, doc.id),
        )
        return ok(payload.model_dump())

    task = asyncio.create_task(document_service.process_document(doc.id))
    try:
        result = await asyncio.wait_for(
            asyncio.shield(task), timeout=document_service.parse_timeout()
        )
    except TimeoutError:
        # 解析超时：任务继续在后台跑，前端轮询 GET /documents/{id}/status（文档 8.1）
        log.warning("parse timeout, continue in background", extra={"document_id": doc.id})
        payload = UploadOut(
            document_id=doc.id,
            status="parsing",
            contract_type=doc.contract_type or "unknown",
            type_source=doc.type_source or "unknown",
            page_count=0,
            clause_count=0,
        )
        return JSONResponse(
            status_code=202,
            headers={SESSION_HEADER: session_id},
            content={
                "code": int(ErrorCode.TASK_IN_PROGRESS),
                "message": "解析中，请轮询文档状态",
                "data": payload.model_dump(),
            },
        )

    if result.status == "failed":
        raise ParseFailed(result.error or "解析失败")

    payload = UploadOut(
        document_id=doc.id,
        status=result.status,
        contract_type=result.contract_type,
        type_source=result.type_source,
        page_count=result.page_count,
        clause_count=result.clause_count,
    )
    return ok(payload.model_dump())


@router.get("/{document_id}", summary="查询文档与条款（8.2）")
async def get_document(
    document_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    session_id = _require_session(x_session_id)
    doc = await document_service.get_document(session, document_id, session_id)
    return ok(to_detail(doc).model_dump())


@router.get("/{document_id}/status", summary="轮询解析状态（8.1 补充）")
async def get_status(
    document_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    session_id = _require_session(x_session_id)
    doc = await document_service.get_document(session, document_id, session_id)
    return ok(
        {
            "document_id": doc.id,
            "status": doc.status,
            "contract_type": doc.contract_type or "unknown",
            "page_count": doc.page_count,
            "clause_count": len(doc.clauses),
            "error_msg": doc.error_msg,
        }
    )


@router.get("/{document_id}/file", summary="获取原始文件，供前端 pdf.js 渲染（8.3）")
async def get_document_file(
    document_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    session_id = _require_session(x_session_id)
    path, _filename = await document_service.get_file_path(session, document_id, session_id)
    return FileResponse(path, media_type="application/pdf")


@router.delete("/{document_id}", summary="删除文档（8.7）")
async def delete_document(
    document_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    session_id = _require_session(x_session_id)
    deleted = await document_service.delete_document(session, document_id, session_id)
    return ok(DeleteOut(deleted=deleted).model_dump())
