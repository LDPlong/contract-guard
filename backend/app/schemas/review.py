"""审查结果响应模型（文档 8.5）。"""

from __future__ import annotations

import json

from pydantic import BaseModel

from app.models.review import Finding, Review


class LegalBasisOut(BaseModel):
    source: str
    article: str
    quote: str
    chunk_id: str


class FindingOut(BaseModel):
    id: str
    clause_id: str | None = None
    item_id: str | None = None
    risk_level: str
    category: str
    title: str
    reason: str
    legal_basis: list[LegalBasisOut] = []
    suggestion: str
    negotiation_tip: str | None = None
    confidence: float


class ReviewOut(BaseModel):
    id: str
    document_id: str
    status: str
    safety_score: int | None = None
    summary: str | None = None
    model: str | None = None
    prompt_version: str
    checklist_version: str
    latency_ms: int | None = None
    findings: list[FindingOut] = []


def _basis(raw: str) -> list[LegalBasisOut]:
    try:
        items = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [LegalBasisOut(**item) for item in items if isinstance(item, dict)]


def to_finding_out(row: Finding) -> FindingOut:
    return FindingOut(
        id=row.id,
        clause_id=row.clause_id,
        item_id=row.item_id,
        risk_level=row.risk_level,
        category=row.category,
        title=row.title,
        reason=row.reason,
        legal_basis=_basis(row.legal_basis_json),
        suggestion=row.suggestion,
        negotiation_tip=row.negotiation_tip,
        confidence=round(row.confidence, 3),
    )


def to_review_out(review: Review) -> ReviewOut:
    order = {"high": 3, "medium": 2, "low": 1, "none": 0}
    findings = sorted(
        review.findings, key=lambda f: order.get(f.risk_level, 0), reverse=True
    )
    return ReviewOut(
        id=review.id,
        document_id=review.document_id,
        status=review.status,
        safety_score=review.safety_score,
        summary=review.summary,
        model=review.model,
        prompt_version=review.prompt_version,
        checklist_version=review.checklist_version,
        latency_ms=review.latency_ms,
        findings=[to_finding_out(f) for f in findings],
    )
