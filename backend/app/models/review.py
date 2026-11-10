"""审查与结论 ORM（文档 6.1 reviews / findings）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # 0-100，越高越安全（扣分制算出来的，命名不能叫 risk_score）
    safety_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    checklist_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    demo_mode: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    findings: Mapped[list[Finding]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    review_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    clause_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("clauses.id", ondelete="CASCADE"), nullable=True
    )
    # 对应清单项，便于按审查项统计命中率（文档 DDL 未列，实现补充）
    item_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    negotiation_tip: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    review: Mapped[Review] = relationship(back_populates="findings")

    __table_args__ = (Index("idx_findings_review", "review_id", "risk_level"),)
