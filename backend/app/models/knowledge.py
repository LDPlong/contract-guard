"""法规知识库 ORM（文档 6.1 knowledge_docs）。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    # 主键用确定性 id（如 civil_code:585），保证 chunk_id 跨次构建稳定、可溯源
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    article_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 去掉 UNIQUE：不同条文可能内容相同（短条文/被拆分的片段），
    # 幂等性由 build_index 的"先清空再全量写入"保证，比内容约束更可靠。
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    # 条号整数与法规顺序：字符串排"第十条"会排在"第二条"前，必须用整数排
    article_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    doc_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
