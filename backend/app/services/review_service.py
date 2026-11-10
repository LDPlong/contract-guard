"""审查服务：SSE 编排 + 结果落库（文档 8.3 / 8.4）。

要点：
- 生成器内部使用独立 session（请求 session 在响应开始后就关闭了）
- 先建 review 行再流式推送，前端拿到 review_id 才能回查
- 任何异常都转成 error 事件，不把栈抛给前端
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import ContractType, ErrorCode, RiskLevel
from app.core.errors import BizError
from app.core.logging import get_logger
from app.models.base import SessionLocal
from app.models.document import Clause as ClauseORM
from app.models.document import Document
from app.models.review import Finding as FindingORM
from app.models.review import Review
from app.services.agent import run_review
from app.services.agent.prompts import PROMPT_VERSION
from app.services.llm.client import LLMClient
from app.services.parsing.models import Clause
from app.services.rag.retriever import Retriever

log = get_logger(__name__)

# 便于测试注入假实现
llm_client_factory = LLMClient
retriever_factory = Retriever


def sse_frame(event: str, data: dict) -> str:
    """SSE 帧：event + 单行 data。data 内不允许出现裸换行。"""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _to_dataclass(rows: list[ClauseORM]) -> list[Clause]:
    result: list[Clause] = []
    for row in rows:
        bbox = None
        if row.bbox_json:
            try:
                bbox = tuple(float(v) for v in json.loads(row.bbox_json))  # type: ignore[assignment]
            except (json.JSONDecodeError, TypeError, ValueError):
                bbox = None
        result.append(
            Clause(
                seq=row.seq,
                clause_no=row.clause_no,
                heading_kind=None,
                page_no=row.page_no,
                bbox=bbox,  # type: ignore[arg-type]
                text=row.text,
                char_start=row.char_start or 0,
                char_end=row.char_end or 0,
            )
        )
    return result


async def _create_review(session: AsyncSession, document: Document) -> Review:
    review = Review(
        document_id=document.id,
        status="running",
        prompt_version=PROMPT_VERSION,
        checklist_version="",
        started_at=datetime.now(),
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def _persist_result(
    session: AsyncSession,
    review: Review,
    payload: dict,
    clause_id_by_seq: dict[int, str],
    model_name: str,
    latency_ms: int,
) -> None:
    review.status = "partial" if payload.get("needs_review") else "done"
    review.safety_score = payload.get("safety_score")
    review.summary = payload.get("summary")
    review.model = model_name
    review.checklist_version = payload.get("checklist_version", "")
    review.latency_ms = latency_ms
    review.finished_at = datetime.now()

    for item in payload.get("findings", []):
        seq = item.get("clause_seq")
        clause_id = clause_id_by_seq.get(seq) if isinstance(seq, int) else None
        session.add(
            FindingORM(
                review_id=review.id,
                clause_id=clause_id,
                item_id=item.get("item_id"),
                risk_level=item.get("risk_level", RiskLevel.NONE),
                category=item.get("category", "其他")[:16],
                title=item.get("title", "")[:64],
                reason=item.get("reason", ""),
                legal_basis_json=json.dumps(
                    item.get("legal_basis", []), ensure_ascii=False
                ),
                suggestion=item.get("suggestion", ""),
                negotiation_tip=item.get("negotiation_tip"),
                confidence=float(item.get("confidence") or 0.0),
            )
        )
    await session.commit()


async def stream_review(document_id: str) -> AsyncIterator[str]:
    """产出 SSE 帧。调用前必须已完成文档状态与类型校验。"""
    started = time.perf_counter()
    review_id: str | None = None

    async with SessionLocal() as session:
        doc = await session.scalar(
            select(Document)
            .options(selectinload(Document.clauses))
            .where(Document.id == document_id)
        )
        if doc is None:
            yield sse_frame("error", {"code": int(ErrorCode.NOT_FOUND), "message": "文档不存在"})
            return

        clauses = _to_dataclass(sorted(doc.clauses, key=lambda c: c.seq))
        clause_id_by_seq = {c.seq: c.id for c in doc.clauses}
        full_text = "\n".join(c.text for c in clauses)

        review = await _create_review(session, doc)
        review_id = review.id
        # 不在这里单独发 plan：run_review 首条事件就是 plan，重复会让前端渲染两次
        client = llm_client_factory()
        model_name = client.settings.llm_model

        try:
            async for event in run_review(
                clauses=clauses,
                full_text=full_text,
                contract_type=doc.contract_type or ContractType.UNKNOWN,
                retriever=retriever_factory(),
                client=client,
            ):
                if event["event"] == "done":
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    payload = event["data"]
                    await _persist_result(
                        session, review, payload, clause_id_by_seq, model_name, latency_ms
                    )
                    payload = {
                        **payload,
                        "review_id": review_id,
                        "document_id": document_id,
                        "latency_ms": latency_ms,
                    }
                    yield sse_frame("done", payload)
                    return
                yield sse_frame(event["event"], event["data"])
        except Exception as exc:  # noqa: BLE001
            log.exception("review stream failed document=%s", document_id)
            review.status = "failed"
            review.finished_at = datetime.now()
            await session.commit()
            yield sse_frame(
                "error",
                {
                    "code": int(ErrorCode.LLM_FAILED),
                    "message": f"审查中断：{type(exc).__name__}",
                    "review_id": review_id,
                },
            )


async def get_review(session: AsyncSession, review_id: str, session_id: str) -> Review:
    review = await session.scalar(
        select(Review)
        .options(selectinload(Review.findings))
        .join(Document, Document.id == Review.document_id)
        .where(Review.id == review_id, Document.session_id == session_id)
    )
    if review is None:
        raise BizError(ErrorCode.NOT_FOUND, "审查记录不存在")
    return review
