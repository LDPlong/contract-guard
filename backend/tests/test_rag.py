"""RAG 索引与检索测试（不依赖真实语料文件）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.rag.indexer import Chunk, parse_corpus_file, write_index
from app.services.rag.retriever import Retriever
from app.services.rag.types import tokenize

SAMPLE_MD = """# 测试法典
<!-- source: 测试法 | version: 1.0 | effective: 2021-01-01 | fetched: 2026-11-10 -->

## 第一条
为了保护当事人的合法权益，制定本法。

## 第二条
租赁期限届满，承租人应当返还租赁物。

## 第三条
用人单位与劳动者约定试用期的，试用期不得超过六个月。
"""


def test_parse_corpus_file():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test_law.md"
        path.write_text(SAMPLE_MD, encoding="utf-8")
        chunks = parse_corpus_file(path)

    assert len(chunks) == 3
    assert chunks[0].id == "test_law:一"
    assert chunks[0].article_no == "第一条"
    assert chunks[0].source == "测试法"
    assert chunks[0].title == "测试法典"
    assert chunks[0].effective_date == "2021-01-01"
    assert all(c.checksum for c in chunks)


def test_parse_corpus_splits_long_article():
    import tempfile

    long_body = "\n".join(["这是一段用于测试切分的较长条文内容。" * 3 for _ in range(30)])
    content = f"# 长法典\n<!-- source: 长法 | version: 1 | effective: 2021-01-01 -->\n\n## 第九十九条\n{long_body}\n"

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "long_law.md"
        path.write_text(content, encoding="utf-8")
        chunks = parse_corpus_file(path)

    assert len(chunks) > 1
    assert chunks[0].id.endswith("#1")
    assert all(c.article_no == "第九十九条" for c in chunks)


def build_temp_index(tmp_path: Path) -> Path:
    chunks = [
        Chunk("t:一", "t", "测试法", "测试法典", "第一条", "1.0", None, "租赁期限届满，承租人应当返还租赁物。", "a1"),
        Chunk("t:二", "t", "测试法", "测试法典", "第二条", "1.0", None, "用人单位约定试用期不得超过六个月。", "a2"),
        Chunk("t:三", "t", "测试法", "测试法典", "第三条", "1.0", None, "违约金过分高于损失时，可以请求适当减少。", "a3"),
    ]
    write_index(chunks, tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_retriever_hits_expected_article(tmp_path):
    index_dir = build_temp_index(tmp_path)
    retriever = Retriever(index_dir=index_dir)

    hits = await retriever.search("租赁物 返还", top_k=2)

    assert hits
    assert hits[0].article_no == "第一条"
    assert hits[0].source == "测试法"


@pytest.mark.asyncio
async def test_retriever_returns_empty_for_no_match(tmp_path):
    index_dir = build_temp_index(tmp_path)
    retriever = Retriever(index_dir=index_dir)

    hits = await retriever.search("量子纠缠 超导材料", top_k=3)
    assert hits == []


@pytest.mark.asyncio
async def test_retriever_scores_are_descending(tmp_path):
    index_dir = build_temp_index(tmp_path)
    retriever = Retriever(index_dir=index_dir)

    hits = await retriever.search("试用期 六个月", top_k=3)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_retriever_available_flag(tmp_path):
    assert Retriever(index_dir=tmp_path / "missing").available is False


def test_tokenize_drops_punctuation():
    tokens = tokenize("租赁期限届满，承租人应当返还租赁物。")
    assert "租赁" in tokens or "租赁期限" in tokens
    assert "，" not in tokens
    assert "。" not in tokens
