"""检索层的公共类型与分词。"""

from __future__ import annotations

import re
from dataclasses import dataclass

import jieba

_PUNCT = re.compile(r"[\s\u3000,，。、；;：:！!？?（）()《》“”\"'‘’\-—…·]+")
_jieba_ready = False


def init_jieba() -> None:
    """首次调用时加载词典；关闭 jieba 的启动日志。"""
    global _jieba_ready
    if not _jieba_ready:
        jieba.setLogLevel(20)
        jieba.initialize()
        _jieba_ready = True


def tokenize(text: str) -> list[str]:
    """中文分词 + 去标点，保留长度 ≥ 2 的词与单字数字。"""
    init_jieba()
    cleaned = _PUNCT.sub(" ", text)
    tokens: list[str] = []
    for word in jieba.cut_for_search(cleaned):
        word = word.strip()
        if len(word) >= 2 or word.isdigit():
            tokens.append(word)
    return tokens


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    score: float
    article_no: str
    source: str
    effective_date: str | None = None

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": round(self.score, 4),
            "article_no": self.article_no,
            "source": self.source,
            "effective_date": self.effective_date,
        }
