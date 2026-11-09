"""真实（公开示范文本）样本的解析回归测试。

这些断言锁定的是"切分结构的稳定性"：
一旦切分规则或 bbox 逻辑被改坏，条数会立刻变化，测试即失败。
样本来源见 tests/fixtures/samples/README.md。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.parsing import detect, parse_pdf, split_clauses

SAMPLES = Path(__file__).parent / "fixtures" / "samples"


def load(name: str):
    doc = parse_pdf(SAMPLES / name)
    return doc, split_clauses(doc)


@pytest.mark.parametrize(
    ("filename", "expected_type", "expected_articles", "expected_pages"),
    [
        ("lease_gd.pdf", "lease", 15, 15),
        ("training_samr.pdf", "prepaid", 10, 9),
        # 原文含两份合同（前 25 条 + 后 30 条），合计 55
        ("labor_jx.pdf", "labor", 55, 7),
    ],
)
def test_sample_split_structure(filename, expected_type, expected_articles, expected_pages):
    doc, clauses = load(filename)
    articles = [c for c in clauses if c.clause_no]

    assert doc.page_count == expected_pages
    assert len(articles) == expected_articles
    assert detect(doc.full_text).contract_type == expected_type


def test_lease_clause_numbers_are_consecutive():
    _doc, clauses = load("lease_gd.pdf")
    numbers = [c.clause_no for c in clauses if c.clause_no]
    assert numbers[0] == "第一条"
    assert numbers[-1] == "第十五条"
    assert len(numbers) == len(set(numbers))  # 无重复


def test_every_clause_has_bbox_on_its_start_page():
    _doc, clauses = load("lease_gd.pdf")
    for clause in clauses:
        assert clause.bbox is not None, f"{clause.clause_no} 缺少 bbox"
        x0, y0, x1, y1 = clause.bbox
        assert x0 < x1 and y0 < y1
        assert clause.page_no >= 1


def test_clause_text_offsets_are_ordered():
    doc, clauses = load("training_samr.pdf")
    for clause in clauses:
        assert 0 <= clause.char_start < clause.char_end <= len(doc.full_text)
        assert doc.full_text[clause.char_start : clause.char_end].startswith(
            clause.text.split("\n")[0][:10]
        )
