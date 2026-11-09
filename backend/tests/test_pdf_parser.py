"""PDF 解析测试：用 PyMuPDF 现场生成 PDF，验证文本行抽取与坐标回填。"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from app.core.errors import ParseFailed
from app.services.parsing.pdf_parser import parse_pdf, union_bbox

SAMPLE_LINES = [
    "Article 1 The landlord leases the house to the tenant.",
    "Article 2 The deposit equals one month rent.",
    "Article 3 The lease term is one year.",
]


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in SAMPLE_LINES:
        page.insert_text((72, y), line, fontsize=11)
        y += 22
    doc.save(path)
    doc.close()
    return path


def test_parse_extracts_all_lines_in_order(sample_pdf: Path):
    parsed = parse_pdf(sample_pdf)

    assert parsed.page_count == 1
    assert parsed.pages[0].width == pytest.approx(595, abs=1)
    assert len(parsed.lines) == len(SAMPLE_LINES)
    assert parsed.lines[0].text.startswith("Article 1")
    assert parsed.lines[-1].text.startswith("Article 3")


def test_parse_bbox_within_page_and_normalized_direction(sample_pdf: Path):
    parsed = parse_pdf(sample_pdf)
    width = parsed.pages[0].width
    height = parsed.pages[0].height

    for line in parsed.lines:
        x0, y0, x1, y1 = line.bbox
        assert 0 <= x0 < x1 <= width + 1
        assert 0 <= y0 < y1 <= height + 1
        # 左上原点、y 向下：先出现的行 y0 更小
    assert parsed.lines[0].bbox[1] < parsed.lines[-1].bbox[1]


def test_char_offsets_match_full_text(sample_pdf: Path):
    parsed = parse_pdf(sample_pdf)

    for line in parsed.lines:
        assert parsed.full_text[line.char_start : line.char_end] == line.text


def test_missing_file_raises_parse_failed(tmp_path: Path):
    with pytest.raises(ParseFailed):
        parse_pdf(tmp_path / "not-exist.pdf")


def test_empty_pdf_raises_parse_failed(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()

    with pytest.raises(ParseFailed):
        parse_pdf(path)


def test_union_bbox():
    assert union_bbox([]) is None
    assert union_bbox([(1, 2, 3, 4), (0, 5, 6, 7)]) == (0, 2, 6, 7)
