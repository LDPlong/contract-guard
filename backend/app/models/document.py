"""文档与条款 ORM（文档 6.1 数据模型）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    type_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    # 每页尺寸，供前端 pdf.js 换算缩放比；DDL 未列，属 v1.1 实现的必要补充
    pages_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploaded")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    clauses: Mapped[list[Clause]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Clause.seq",
    )

    __table_args__ = (Index("idx_documents_session", "session_id", "created_at"),)


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    clause_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # [x0,y0,x1,y1]，单位 PDF point，左上原点，绝对坐标（文档 9.2）
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped[Document] = relationship(back_populates="clauses")

    __table_args__ = (Index("idx_clauses_doc", "document_id", "seq"),)
