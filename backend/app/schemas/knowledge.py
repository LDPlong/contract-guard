"""资料库响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class ArticleOut(BaseModel):
    id: str
    source: str
    title: str
    article_no: str
    article_index: int
    version: str | None = None
    effective_date: str | None = None
    content: str


class ArticleListOut(BaseModel):
    total: int
    items: list[ArticleOut]


class SearchHitOut(BaseModel):
    chunk_id: str
    source: str
    article_no: str
    content: str
    score: float
    effective_date: str | None = None


class SearchOut(BaseModel):
    query: str
    total: int
    items: list[SearchHitOut]
