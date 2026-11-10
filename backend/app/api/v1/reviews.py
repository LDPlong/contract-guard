"""审查接口（文档 8.3 / 8.5）。

SSE 走 POST，前端必须用 fetch + ReadableStream 读取，不能用 EventSource。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SUPPORTED_CONTRACT_TYPES, ErrorCode
from app.core.errors import BizError, ParseFailed, UnsupportedContractType, ok
from app.core.logging import get_logger
from app.models.base import get_session
from app.schemas.review import to_review_out
from app.services import document_service, review_service

router = APIRouter(tags=["reviews"])
log = get_logger(__name__)

SESSION_HEADER = "X-Session-Id"

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # 关掉 Nginx 等反代的缓冲，否则事件会被攒着一次性吐出
    "X-Accel-Buffering": "no",
}


@router.post("/documents/{document_id}/review", summary="发起审查（SSE，8.3）")
async def start_review(
    document_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    if not x_session_id:
        raise BizError(ErrorCode.SESSION_INVALID, "缺少 X-Session-Id")

    doc = await document_service.get_document(session, document_id, x_session_id)
    if doc.status == "parsing":
        raise BizError(ErrorCode.TASK_IN_PROGRESS, "文档仍在解析，请稍后重试")
    if doc.status == "failed":
        raise ParseFailed(doc.error_msg or "文档解析失败，请重新上传")
    if doc.contract_type not in SUPPORTED_CONTRACT_TYPES:
        raise UnsupportedContractType("暂不支持该合同类型，无法进入审查")

    return StreamingResponse(
        review_service.stream_review(document_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/reviews/{review_id}", summary="查询审查结果（8.5）")
async def get_review(
    review_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    if not x_session_id:
        raise BizError(ErrorCode.SESSION_INVALID, "缺少 X-Session-Id")
    review = await review_service.get_review(session, review_id, x_session_id)
    return ok(to_review_out(review).model_dump())


@router.get("/documents/{document_id}/reviews", summary="文档的历史审查记录")
async def list_reviews(
    document_id: str,
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
    session: AsyncSession = Depends(get_session),
):
    if not x_session_id:
        raise BizError(ErrorCode.SESSION_INVALID, "缺少 X-Session-Id")
    await document_service.get_document(session, document_id, x_session_id)

    from sqlalchemy import select

    from app.models.review import Review

    rows = (
        await session.scalars(
            select(Review)
            .where(Review.document_id == document_id)
            .order_by(Review.started_at.desc())
        )
    ).all()
    return ok(
        [
            {
                "review_id": r.id,
                "status": r.status,
                "safety_score": r.safety_score,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in rows
        ]
    )

