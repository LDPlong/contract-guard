"""资料库接口测试：分页、条号排序、检索。"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import BACKEND_DIR, get_settings
from app.main import app
from app.models.base import SessionLocal, init_models
from app.models.knowledge import KnowledgeDoc
from app.services.rag.indexer import parse_corpus_file, write_index

CORPUS_DIR = BACKEND_DIR / "app" / "data" / "corpus"


async def _seed() -> None:
    """把仓库内的语料灌进测试库并建索引，保证资料库测试不依赖开发数据。"""
    await init_models()
    chunks = []
    for order, path in enumerate(sorted(CORPUS_DIR.glob("*.md"))):
        chunks.extend(parse_corpus_file(path, doc_order=order))

    async with SessionLocal() as session:
        session.add_all(
            [
                KnowledgeDoc(
                    id=c.id,
                    source=c.source,
                    title=c.title,
                    article_no=c.article_no,
                    version=c.version or None,
                    content=c.content,
                    checksum=c.checksum,
                    article_index=c.article_index,
                    doc_order=c.doc_order,
                )
                for c in chunks
            ]
        )
        await session.commit()

    write_index(chunks, get_settings().index_path)


@pytest.fixture(scope="module", autouse=True)
def seed_corpus():
    if not CORPUS_DIR.is_dir():
        pytest.skip("语料目录不存在")
    asyncio.run(_seed())
    yield


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_sources_list(client):
    resp = await client.get("/api/v1/knowledge/sources")
    assert resp.status_code == 200

    items = resp.json()["data"]["items"]
    assert items, "资料库为空，请先运行 build_index"
    names = {i["source"] for i in items}
    assert "民法典" in names
    # 条数按条号去重，不应是 chunk 数
    civil = next(i for i in items if i["source"] == "民法典")
    assert civil["count"] == 1260


@pytest.mark.asyncio
async def test_articles_sorted_by_article_index(client):
    resp = await client.get(
        "/api/v1/knowledge/articles", params={"source": "民法典", "limit": 3}
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["total"] == 1260
    assert [a["article_index"] for a in data["items"]] == [1, 2, 3]
    assert data["items"][0]["article_no"] == "第一条"


@pytest.mark.asyncio
async def test_articles_keyword_filter(client):
    resp = await client.get(
        "/api/v1/knowledge/articles", params={"q": "违约金", "limit": 5}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] > 0
    assert all("违约金" in a["content"] for a in data["items"])


@pytest.mark.asyncio
async def test_article_detail_404(client):
    resp = await client.get("/api/v1/knowledge/articles/not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_returns_hits(client):
    resp = await client.get(
        "/api/v1/knowledge/search", params={"q": "租赁期限届满 返还租赁物", "top_k": 3}
    )
    assert resp.status_code == 200

    items = resp.json()["data"]["items"]
    assert items
    assert any("第七百三十三条" == i["article_no"] for i in items)
