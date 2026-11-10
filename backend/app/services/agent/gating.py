"""条款预筛（文档 10.1）。

作用：把"合同里所有条款 × 所有审查项"的笛卡尔积，收敛成几十个真正相关的组合，
否则 token 和耗时都不可控。

策略：关键词命中优先（合同用词比法条更口语），BM25 兜底（覆盖同义表述）。
"""

from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.core.constants import GATE_MIN_SCORE, GATE_TOP_K
from app.services.agent.checklist import ChecklistItem
from app.services.parsing.models import Clause
from app.services.rag.types import tokenize

KEYWORD_WEIGHT = 3.0


@dataclass
class Candidate:
    clause: Clause
    score: float
    keyword_hits: list[str]


class Gate:
    def __init__(
        self,
        clauses: list[Clause],
        top_k: int = GATE_TOP_K,
        min_score: float = GATE_MIN_SCORE,
    ) -> None:
        self.clauses = clauses
        self.top_k = top_k
        self.min_score = min_score
        self._tokens = [tokenize(c.text) for c in clauses]
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None

    def candidates(self, item: ChecklistItem) -> list[Candidate]:
        if not self.clauses or self._bm25 is None:
            return []

        scores = self._bm25.get_scores(tokenize(item.query))
        results: list[Candidate] = []
        for idx, clause in enumerate(self.clauses):
            hits = [kw for kw in item.keywords if kw in clause.text]
            total = float(scores[idx]) + KEYWORD_WEIGHT * len(hits)
            if hits or (scores[idx] > 0 and total >= self.min_score):
                results.append(Candidate(clause=clause, score=total, keyword_hits=hits))

        if not results:
            return []

        results.sort(key=lambda c: c.score, reverse=True)
        # 关键词全空但 BM25 有信号的场景，放宽到 top_k，避免整项被判"不适用"
        return results[: self.top_k]
