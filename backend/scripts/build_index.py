"""构建法规向量与 BM25 索引，并写入 knowledge_docs 表。

幂等：先清空 knowledge_docs 再全量写入（语料只有几千条，全量重建最省心）。
未配置 EMBEDDING_* 时只建 BM25 索引，meta.json 的 dim 记为 0，检索自动降级。

用法：
    python -m scripts.build_index
    python -m scripts.build_index --corpus app/data/corpus --index data/index
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

from sqlalchemy import delete

from app.core.config import get_settings
from app.models.base import SessionLocal, init_models
from app.models.knowledge import KnowledgeDoc
from app.services.rag.embedder import Embedder
from app.services.rag.indexer import Chunk, load_bm25, parse_corpus_file, write_index


def _to_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        year, month, day = (int(x) for x in raw.split("-")[:3])
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


async def _persist(chunks: list[Chunk]) -> int:
    async with SessionLocal() as session:
        await session.execute(delete(KnowledgeDoc))
        session.add_all(
            [
                KnowledgeDoc(
                    id=c.id,
                    source=c.source,
                    title=c.title,
                    article_no=c.article_no,
                    version=c.version or None,
                    effective_date=_to_date(c.effective_date),
                    content=c.content,
                    checksum=c.checksum,
                    article_index=c.article_index,
                    doc_order=c.doc_order,
                )
                for c in chunks
            ]
        )
        await session.commit()
    return len(chunks)


async def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default=str(Path(__file__).parents[1] / "app" / "data" / "corpus"))
    parser.add_argument("--index", default=str(settings.index_path))
    parser.add_argument("--skip-db", action="store_true", help="只建文件索引，不写数据库")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus)
    index_dir = Path(args.index)
    files = sorted(corpus_dir.glob("*.md"))
    if not files:
        raise SystemExit(f"语料目录为空：{corpus_dir}")

    chunks: list[Chunk] = []
    for order, path in enumerate(files):
        parsed = parse_corpus_file(path, doc_order=order)
        print(f"  {path.name}: {len(parsed)} 条")
        chunks.extend(parsed)
    print(f"合计 {len(chunks)} 个 chunk")

    await init_models()
    if not args.skip_db:
        count = await _persist(chunks)
        print(f"knowledge_docs 写入 {count} 行")

    vectors = None
    embedder = Embedder(settings)
    if embedder.available:
        print(f"向量化中（{embedder.model_name}，batch=16）…")
        matrix = await embedder.embed([c.content for c in chunks])
        vectors = {"ids": [c.id for c in chunks], "matrix": matrix}
        print(f"向量矩阵 {matrix.shape}")
    else:
        print("未配置 EMBEDDING_*，跳过向量化：检索将只走 BM25")

    meta = write_index(
        chunks, index_dir, vectors=vectors, model=embedder.model_name if vectors else ""
    )
    print(f"索引已写入 {index_dir}")
    print(
        f"  chunk={meta['chunk_count']} dim={meta['dim']} "
        f"sources={','.join(meta['sources'])} built_at={meta['built_at']}"
    )

    # 自检：能读回即认为索引可用
    data = load_bm25(index_dir)
    assert len(data["ids"]) == meta["chunk_count"], "索引文件与 meta 不一致"
    print("  自检通过")


if __name__ == "__main__":
    asyncio.run(main())
