"""在线检索：BM25 + 向量 + RRF 融合（文档 7.2）。

要点：
- RRF 而不是分数加权：两路分数量纲不同，直接加权会被 BM25 的长尾压死
- 任一通道缺失时自动降级（未配置 embedding → 纯 BM25）
- 检索为空返回 []，由上层输出"未覆盖"，绝不编造法条
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.core.constants import RRF_K
from app.services.rag.embedder import Embedder
from app.services.rag.indexer import load_bm25
from app.services.rag.types import RetrievedChunk, tokenize


class Retriever:
    def __init__(
        self,
        index_dir: Path | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.settings = get_settings()
        settings = self.settings
        self.index_dir = index_dir or settings.index_path
        self.embedder = embedder if embedder is not None else Embedder(settings)
        self._data: dict | None = None
        self._bm25: BM25Okapi | None = None
        self._vectors: dict | None = None
        self._meta: dict | None = None
        self._meta_map: dict[str, dict] | None = None

    # ---- 加载 ----
    def _load(self) -> None:
        if self._bm25 is not None:
            return
        self._data = load_bm25(self.index_dir)
        self._bm25 = BM25Okapi(self._data["tokens"])

        meta_path = self.index_dir / "meta.json"
        self._meta = json.loads(meta_path.read_text("utf-8")) if meta_path.is_file() else {}

        vec_path = self.index_dir / "vectors.npz"
        if vec_path.is_file():
            loaded = np.load(vec_path, allow_pickle=False)
            self._vectors = {"ids": list(loaded["ids"]), "matrix": loaded["matrix"]}

    @property
    def available(self) -> bool:
        return (self.index_dir / "bm25.pkl").is_file()

    @property
    def chunk_count(self) -> int:
        self._load()
        return int((self._meta or {}).get("chunk_count", 0))

    @property
    def has_vector_channel(self) -> bool:
        self._load()
        return self._vectors is not None and self.embedder.available

    # ---- 单通道召回 ----
    def _bm25_rank(self, query: str, top_k: int) -> list[tuple[int, float]]:
        assert self._bm25 is not None and self._data is not None
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        order = np.argsort(scores)[::-1][: top_k * 3]
        return [(int(i), float(scores[i])) for i in order if scores[i] > 0][:top_k]

    async def _vector_rank(self, query: str, top_k: int) -> list[tuple[int, float]]:
        if self._vectors is None:
            return []
        query_vec = await self.embedder.embed([query])
        sims = self._vectors["matrix"] @ query_vec[0]
        order = np.argsort(sims)[::-1][:top_k]
        return [(int(i), float(sims[i])) for i in order]

    # ---- 对外 ----
    async def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or self.settings.rerank_top_n
        self._load()
        assert self._data is not None

        bm25_hits = self._bm25_rank(query, top_k * 4)
        vector_hits: list[tuple[int, float]] = []
        if self.has_vector_channel:
            try:
                vector_hits = await self._vector_rank(query, top_k * 4)
            except Exception:  # noqa: BLE001
                vector_hits = []  # 向量通道失败不影响主流程

        if not bm25_hits and not vector_hits:
            return []

        # RRF 融合：按名次而非分数累加
        fused: dict[int, float] = {}
        for rank, (idx, _score) in enumerate(bm25_hits):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, (idx, _score) in enumerate(vector_hits):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        ids = self._data["ids"]
        contents = self._data["contents"]
        meta_by_id = self._meta_by_id()

        results: list[RetrievedChunk] = []
        for idx, score in ranked:
            chunk_id = ids[idx]
            info = meta_by_id.get(chunk_id, {})
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    content=contents[idx],
                    score=score,
                    article_no=info.get("article_no", ""),
                    source=info.get("source", ""),
                    effective_date=info.get("effective_date"),
                )
            )
        return results

    def _meta_by_id(self) -> dict[str, dict]:
        """chunk_id → 元信息。由 build_index 写入 sidecar，缺失时退化为空。"""
        if self._meta_map is not None:
            return self._meta_map
        path = self.index_dir / "chunks_meta.json"
        self._meta_map = json.loads(path.read_text("utf-8")) if path.is_file() else {}
        return self._meta_map
