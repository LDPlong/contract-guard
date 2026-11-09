"""解析层的中间数据结构。

设计原则：解析器只产出"带坐标的文本行"，切分器只消费文本行。
两者通过本模块解耦，便于单元测试不依赖真实 PDF。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BBox = tuple[float, float, float, float]  # (x0, y0, x1, y1)，单位 PDF point

HeadingKind = Literal["clause", "paragraph", "numbered", "paren"]


@dataclass(frozen=True)
class TextLine:
    """一行文本，携带页码、坐标与全文偏移。"""

    page_no: int
    bbox: BBox
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class PageInfo:
    page_no: int
    width: float
    height: float


@dataclass
class ParsedDocument:
    page_count: int
    pages: list[PageInfo]
    lines: list[TextLine]
    full_text: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class Clause:
    """切分产物。bbox 只覆盖条款起始页（文档 9.2 约定）。"""

    seq: int
    clause_no: str | None
    heading_kind: HeadingKind | None
    page_no: int
    bbox: BBox | None
    text: str
    char_start: int
    char_end: int

    @property
    def text_length(self) -> int:
        return len(self.text)
