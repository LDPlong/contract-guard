"""Embedding 封装（仅在配置了 EMBEDDING_* 时启用）。

未配置时上层自动降级为纯 BM25 检索，不影响可用性。
"""

from __future__ import annotations

import numpy as np
from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.errors import LLMFailed


class Embedder:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: AsyncOpenAI | None = None

    @property
    def available(self) -> bool:
        s = self.settings
        return bool(s.embedding_base_url and s.embedding_api_key and s.embedding_model)

    def _ensure(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.available:
                raise LLMFailed("未配置 Embedding（EMBEDDING_BASE_URL / API_KEY / MODEL）")
            self._client = AsyncOpenAI(
                base_url=self.settings.embedding_base_url,
                api_key=self.settings.embedding_api_key,
                timeout=self.settings.llm_timeout,
                max_retries=1,
            )
        return self._client

    async def embed(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        """批量向量化并做 L2 归一化（归一化后点积即余弦相似度）。"""
        client = self._ensure()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            resp = await client.embeddings.create(
                model=self.settings.embedding_model, input=batch
            )
            vectors.extend(item.embedding for item in resp.data)

        matrix = np.asarray(vectors, dtype="float32")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    @property
    def model_name(self) -> str:
        return self.settings.embedding_model
