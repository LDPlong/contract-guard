"""文档相关响应模型（文档 8.1 / 8.2）。"""

from __future__ import annotations

import json

from pydantic import BaseModel

from app.models.document import Document


class PageOut(BaseModel):
    page_no: int
    width: float
    height: float


class ClauseOut(BaseModel):
    id: str
    seq: int
    clause_no: str | None = None
    page_no: int
    bbox: list[float] | None = None
    text: str


class DocumentDetailOut(BaseModel):
    id: str
    filename: str
    contract_type: str
    status: str
    pages: list[PageOut]
    clauses: list[ClauseOut]


class UploadOut(BaseModel):
    document_id: str
    status: str
    contract_type: str
    type_source: str
    page_count: int
    clause_count: int


class DeleteOut(BaseModel):
    deleted: bool


def _load_bbox(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return [float(v) for v in value] if isinstance(value, list) and len(value) == 4 else None


def to_detail(doc: Document) -> DocumentDetailOut:
    pages = json.loads(doc.pages_json) if doc.pages_json else []
    return DocumentDetailOut(
        id=doc.id,
        filename=doc.filename,
        contract_type=doc.contract_type or "unknown",
        status=doc.status,
        pages=[PageOut(**p) for p in pages],
        clauses=[
            ClauseOut(
                id=c.id,
                seq=c.seq,
                clause_no=c.clause_no,
                page_no=c.page_no,
                bbox=_load_bbox(c.bbox_json),
                text=c.text,
            )
            for c in doc.clauses
        ],
    )
