"""条款级切分（核心算法，文档第 9 节）。

输入：带坐标的文本行；输出：带编号、页码、bbox、全文偏移的条款。

关于"短段合并"（文档 9 规则 3）：本实现按"标题开启新块、后续行归入同一块"处理，
标题天生不会与正文分离，因此不需要单独的合并步骤；该规则转化为对**孤立短行**的处理——
若某行既不是标题、字数又少于阈值，直接并入当前块而不是另起一段。
"""

from __future__ import annotations

import re

from app.services.parsing.models import Clause, HeadingKind, ParsedDocument, TextLine
from app.services.parsing.pdf_parser import union_bbox

# 顺序即优先级：先认"第X条"，再认款/阿拉伯编号/括号编号
HEADING_PATTERNS: list[tuple[HeadingKind, re.Pattern[str]]] = [
    ("clause", re.compile(r"^\s*(第[一二三四五六七八九十百零〇]{1,6}条)")),
    ("paragraph", re.compile(r"^\s*(第[一二三四五六七八九十]{1,4}款)")),
    ("numbered", re.compile(r"^\s*(\d{1,2}(?:[.．]\d{1,2}){0,3})(?:[、.．]\s*|\s+)")),
    ("paren", re.compile(r"^\s*([（(][一二三四五六七八九十]{1,3}[)）])")),
]

MIN_PREAMBLE_CHARS = 4  # 保留合同标题等前置内容，过短（页码、页眉残字）则丢弃
FALLBACK_CHUNK_CHARS = 600
SHORT_LINE_CHARS = 30
SENTENCE_END = ("。", "！", "？", "；", ";", "!", "?")


def _match_heading(text: str) -> tuple[HeadingKind, str] | None:
    """返回 (类型, 编号原文)；不是标题行返回 None。"""
    stripped = text.strip()
    if len(stripped) < 2:
        return None
    for kind, pattern in HEADING_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return kind, match.group(1)
    return None


def _build_clause(
    lines: list[TextLine],
    seq: int,
    heading_kind: HeadingKind | None,
    clause_no: str | None,
) -> Clause:
    start_page = lines[0].page_no
    same_page_boxes = [ln.bbox for ln in lines if ln.page_no == start_page]
    return Clause(
        seq=seq,
        clause_no=clause_no,
        heading_kind=heading_kind,
        page_no=start_page,
        bbox=union_bbox(same_page_boxes),
        text="\n".join(ln.text for ln in lines),
        char_start=lines[0].char_start,
        char_end=lines[-1].char_end,
    )


def _fallback_split(lines: list[TextLine]) -> list[Clause]:
    """全文没有任何编号时的兜底：按句末标点 + 长度上限切块。"""
    chunks: list[list[TextLine]] = []
    current: list[TextLine] = []
    for line in lines:
        current.append(line)
        size = sum(len(ln.text) for ln in current)
        if size >= FALLBACK_CHUNK_CHARS or line.text.rstrip().endswith(SENTENCE_END):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return [_build_clause(chunk, idx, None, None) for idx, chunk in enumerate(chunks, start=1)]


def split_clauses(
    doc: ParsedDocument,
    min_preamble_chars: int = MIN_PREAMBLE_CHARS,
) -> list[Clause]:
    """把文本行切分为条款列表。返回结果 seq 从 1 递增，无编号时 clause_no 为 None。"""
    lines = doc.lines
    if not lines:
        return []

    headings: list[tuple[int, HeadingKind, str]] = []
    for idx, line in enumerate(lines):
        matched = _match_heading(line.text)
        if matched:
            headings.append((idx, matched[0], matched[1]))

    if not headings:
        return _fallback_split(lines)

    clauses: list[Clause] = []
    first_heading_idx = headings[0][0]
    if first_heading_idx > 0:
        preamble = lines[:first_heading_idx]
        if sum(len(ln.text) for ln in preamble) >= min_preamble_chars:
            clauses.append(_build_clause(preamble, seq=1, heading_kind=None, clause_no=None))

    for pos, (start_idx, kind, no) in enumerate(headings):
        end_idx = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
        block = lines[start_idx:end_idx]
        clauses.append(
            _build_clause(block, seq=len(clauses) + 1, heading_kind=kind, clause_no=no)
        )

    return clauses


def split_text_lines(
    lines: list[TextLine],
    min_preamble_chars: int = MIN_PREAMBLE_CHARS,
) -> list[Clause]:
    """仅凭文本行切分（便于测试与 OCR 结果复用，不依赖完整 ParsedDocument）。"""
    doc = ParsedDocument(
        page_count=max((ln.page_no for ln in lines), default=0),
        pages=[],
        lines=lines,
        full_text="\n".join(ln.text for ln in lines),
    )
    return split_clauses(doc, min_preamble_chars=min_preamble_chars)
