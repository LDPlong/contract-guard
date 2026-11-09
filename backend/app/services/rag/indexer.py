"""语料解析与索引落盘。

语料格式（由 scripts/import_law_corpus.py 生成）：
    # 法规标题
    <!-- source: xxx | version: xxx | effective: xxx | fetched: xxx -->

    ## 第五百八十五条
    正文……

索引产物（INDEX_DIR）：
    bm25.pkl      {"ids": [...], "tokens": [[...]], "contents": [...]}
    vectors.npz   {"ids": [...], "matrix": float32[N,dim]}（仅在配置了 embedding 时）
    meta.json     {"built_at", "chunk_count", "dim", "model", "corpus_checksum", "sources"}
"""

from __future__ import annotations

import hashlib
import json
import pickle
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.rag.types import tokenize

HEADER_RE = re.compile(r"^#\s+(.+)$", re.M)
META_RE = re.compile(r"<!--\s*(.+?)\s*-->")
ARTICLE_RE = re.compile(r"^##\s+第([零一二三四五六七八九十百千]+)条\s*$", re.M)
MAX_CHUNK_CHARS = 800
OVERLAP_CHARS = 100


@dataclass
class Chunk:
    id: str
    source_key: str
    source: str
    title: str
    article_no: str
    version: str
    effective_date: str | None
    content: str
    checksum: str


def _parse_meta(raw: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for part in raw.split("|"):
        if ":" in part:
            key, value = part.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def _split_long(text: str) -> list[str]:
    """超过 800 字的条文按段落切，保留 100 字重叠，避免语义被切断。"""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    paragraphs = [p for p in text.split("\n") if p.strip()]
    pieces: list[str] = []
    buffer = ""
    for para in paragraphs:
        if buffer and len(buffer) + len(para) > MAX_CHUNK_CHARS:
            pieces.append(buffer)
            buffer = buffer[-OVERLAP_CHARS:] + para
        else:
            buffer = f"{buffer}\n{para}" if buffer else para
    if buffer:
        pieces.append(buffer)
    return pieces


def parse_corpus_file(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    header = HEADER_RE.search(raw)
    title = header.group(1).strip() if header else path.stem

    meta_raw = META_RE.search(raw)
    meta = _parse_meta(meta_raw.group(1)) if meta_raw else {}
    source_key = path.stem
    source = meta.get("source", title)
    version = meta.get("version", "")
    effective = meta.get("effective")

    body = raw[META_RE.sub("", raw, count=1).find("##"):] if "##" in raw else ""
    positions = list(ARTICLE_RE.finditer(body))
    chunks: list[Chunk] = []

    for idx, match in enumerate(positions):
        article_cn = match.group(1)
        end = positions[idx + 1].start() if idx + 1 < len(positions) else len(body)
        content = body[match.end() : end].strip()
        if len(content) < 4:
            continue
        parts = _split_long(content)
        for part_idx, part in enumerate(parts):
            suffix = f"#{part_idx + 1}" if len(parts) > 1 else ""
            chunk_id = f"{source_key}:{article_cn}{suffix}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    source_key=source_key,
                    source=source,
                    title=title,
                    article_no=f"第{article_cn}条",
                    version=version,
                    effective_date=effective,
                    content=part,
                    checksum=hashlib.sha1(part.encode("utf-8")).hexdigest(),
                )
            )
    return chunks


def write_index(
    chunks: list[Chunk],
    index_dir: Path,
    vectors: dict | None = None,
    model: str = "",
) -> dict:
    index_dir.mkdir(parents=True, exist_ok=True)
    ids = [c.id for c in chunks]
    tokens = [tokenize(c.content) for c in chunks]

    with (index_dir / "bm25.pkl").open("wb") as fp:
        pickle.dump(
            {"ids": ids, "tokens": tokens, "contents": [c.content for c in chunks]}, fp
        )

    dim = 0
    if vectors is not None:
        import numpy as np

        np.savez_compressed(
            index_dir / "vectors.npz",
            ids=np.array(vectors["ids"]),
            matrix=vectors["matrix"].astype("float32"),
        )
        dim = int(vectors["matrix"].shape[1])

    corpus_checksum = hashlib.sha1("".join(c.checksum for c in chunks).encode()).hexdigest()
    meta = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "chunk_count": len(chunks),
        "dim": dim,
        "model": model,
        "corpus_checksum": corpus_checksum,
        "sources": sorted({c.source_key for c in chunks}),
    }
    (index_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 检索时按 chunk_id 反查元信息（条号/来源/生效日期）
    sidecar = {
        c.id: {
            "article_no": c.article_no,
            "source": c.source,
            "title": c.title,
            "version": c.version,
            "effective_date": c.effective_date,
        }
        for c in chunks
    }
    (index_dir / "chunks_meta.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def load_bm25(index_dir: Path) -> dict:
    path = index_dir / "bm25.pkl"
    if not path.is_file():
        raise FileNotFoundError("索引未构建：缺少 bm25.pkl，请先运行 scripts/build_index.py")
    with path.open("rb") as fp:
        return pickle.load(fp)
