"""法规资料库接口（文档 8.9 扩展）。

用途：让用户自己去查法条，而不是只看到模型引用的那几条。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ErrorCode
from app.core.errors import BizError
from app.core.logging import get_logger
from app.models.base import get_session
from app.models.knowledge import KnowledgeDoc
from app.schemas.knowledge import ArticleListOut, ArticleOut, SearchOut
from app.services.rag.retriever import Retriever

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
log = get_logger(__name__)

MAX_LIMIT = 100


def _to_out(row: KnowledgeDoc) -> ArticleOut:
    return ArticleOut(
        id=row.id,
        source=row.source,
        title=row.title,
        article_no=row.article_no or "",
        article_index=row.article_index,
        version=row.version,
        effective_date=row.effective_date.isoformat() if row.effective_date else None,
        content=row.content,
    )


@router.get("/sources", summary="法规清单与条数")
async def list_sources(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await session.execute(
        select(
            KnowledgeDoc.source,
            KnowledgeDoc.title,
            KnowledgeDoc.version,
            KnowledgeDoc.effective_date,
            # 按条去重：超长条文会被切成多个 chunk，直接 count 会虚高
            func.count(func.distinct(KnowledgeDoc.article_index)).label("count"),
            func.min(KnowledgeDoc.doc_order).label("order"),
        )
        .group_by(
            KnowledgeDoc.source,
            KnowledgeDoc.title,
            KnowledgeDoc.version,
            KnowledgeDoc.effective_date,
        )
        .order_by("order")
    )
    items = [
        {
            "source": r.source,
            "title": r.title,
            "version": r.version,
            "effective_date": r.effective_date.isoformat() if r.effective_date else None,
            "count": r.count,
        }
        for r in rows
    ]
    return {"code": 0, "message": "ok", "data": {"items": items}}


@router.get("/articles", summary="按法规/关键词分页浏览条文")
async def list_articles(
    source: str | None = Query(default=None, description="法规来源，如 民法典"),
    q: str | None = Query(default=None, description="条文关键词"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=MAX_LIMIT),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(KnowledgeDoc)
    # 超长条文会被切成多个 chunk，条数要按条号去重
    count_stmt = select(func.count(func.distinct(KnowledgeDoc.article_index)))

    if source:
        stmt = stmt.where(KnowledgeDoc.source == source)
        count_stmt = count_stmt.where(KnowledgeDoc.source == source)
    if q:
        pattern = f"%{q.strip()}%"
        condition = KnowledgeDoc.content.like(pattern) | KnowledgeDoc.article_no.like(pattern)
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = int(await session.scalar(count_stmt) or 0)
    rows = (
        await session.scalars(
            stmt.order_by(KnowledgeDoc.doc_order, KnowledgeDoc.article_index)
            .offset(offset)
            .limit(limit)
        )
    ).all()

    payload = ArticleListOut(total=total, items=[_to_out(r) for r in rows])
    return {"code": 0, "message": "ok", "data": payload.model_dump()}


@router.get("/articles/{article_id}", summary="单条法条")
async def get_article(article_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(KnowledgeDoc, article_id)
    if row is None:
        raise BizError(ErrorCode.NOT_FOUND, "法条不存在")
    return {"code": 0, "message": "ok", "data": _to_out(row).model_dump()}


@router.get("/search", summary="语义检索（调试与资料库搜索共用）")
async def search(
    q: str = Query(min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
) -> dict:
    retriever = Retriever()
    if not retriever.available:
        raise BizError(ErrorCode.RETRIEVE_EMPTY, "法规索引未构建，请先运行 build_index")

    hits = await retriever.search(q, top_k=top_k)
    payload = SearchOut(
        query=q,
        total=len(hits),
        items=[
            {
                "chunk_id": h.chunk_id,
                "source": h.source,
                "article_no": h.article_no,
                "content": h.content,
                "score": round(h.score, 5),
                "effective_date": h.effective_date,
            }
            for h in hits
        ],
    )
    return {"code": 0, "message": "ok", "data": payload.model_dump()}
