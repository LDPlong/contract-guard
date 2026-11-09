"""解析层：PDF 抽取 → 条款切分 → 类型识别。"""

from app.services.parsing.clause_splitter import split_clauses, split_text_lines
from app.services.parsing.models import Clause, ParsedDocument, TextLine
from app.services.parsing.pdf_parser import parse_pdf, union_bbox
from app.services.parsing.type_detector import detect, detect_by_rules

__all__ = [
    "Clause",
    "ParsedDocument",
    "TextLine",
    "detect",
    "detect_by_rules",
    "parse_pdf",
    "split_clauses",
    "split_text_lines",
    "union_bbox",
]
