"""条款切分单元测试（不依赖真实 PDF，直接构造带坐标的文本行）。"""

from __future__ import annotations

from app.services.parsing.clause_splitter import split_text_lines
from app.services.parsing.models import TextLine


def make_lines(specs: list[tuple[str, int, float]]) -> list[TextLine]:
    """specs: (文本, 页码, y 坐标)。按 12pt 行高递增生成 bbox。"""
    lines: list[TextLine] = []
    cursor = 0
    for text, page_no, y in specs:
        lines.append(
            TextLine(
                page_no=page_no,
                bbox=(72.0, y, 523.0, y + 14.0),
                text=text,
                char_start=cursor,
                char_end=cursor + len(text),
            )
        )
        cursor += len(text) + 1
    return lines


def test_split_by_article_number():
    lines = make_lines(
        [
            ("房屋租赁合同", 1, 60),
            ("第一条 甲方将位于某市的房屋出租给乙方。", 1, 100),
            ("第二条 租金为每月三千元，押一付三。", 1, 130),
            ("第三条 租赁期限为一年。", 1, 160),
        ]
    )
    clauses = split_text_lines(lines)

    # 前置标题单独成块（长度 ≥ 10 字）
    assert clauses[0].clause_no is None
    assert clauses[0].text == "房屋租赁合同"

    articles = [c for c in clauses if c.clause_no]
    assert [c.clause_no for c in articles] == ["第一条", "第二条", "第三条"]
    assert articles[0].heading_kind == "clause"
    assert articles[0].page_no == 1


def test_multiline_clause_bbox_is_union_on_start_page():
    lines = make_lines(
        [
            ("第一条 甲方将房屋出租给乙方，房屋地址为某市某区某路 1 号。", 1, 100),
            ("乙方确认已实地查看房屋状况。", 1, 116),
            ("第二条 押金为一个月租金。", 2, 100),
        ]
    )
    clauses = split_text_lines(lines)

    first = clauses[0]
    assert "乙方确认已实地查看房屋状况。" in first.text
    # bbox 只取起始页的两行并集，不跨页
    assert first.bbox == (72.0, 100.0, 523.0, 130.0)
    assert clauses[1].page_no == 2


def test_char_offsets_are_monotonic():
    lines = make_lines(
        [
            ("第一条 甲方出租房屋。", 1, 100),
            ("第二条 乙方支付押金。", 1, 130),
        ]
    )
    clauses = split_text_lines(lines)
    assert clauses[0].char_start < clauses[0].char_end
    assert clauses[0].char_end < clauses[1].char_start


def test_no_heading_falls_back_to_chunks():
    lines = make_lines(
        [
            ("这是一段没有任何编号的说明文字。", 1, 100),
            ("仍然没有编号，继续描述双方权利义务。", 1, 116),
        ]
    )
    clauses = split_text_lines(lines)
    assert len(clauses) >= 1
    assert all(c.clause_no is None for c in clauses)
    assert all(c.heading_kind is None for c in clauses)


def test_short_line_not_orphaned():
    """孤立短行（无编号、<30 字）应并入当前块，而不是单独成条。"""
    lines = make_lines(
        [
            ("第一条 租金支付方式如下：", 1, 100),
            ("月付。", 1, 116),
            ("第二条 押金退还。", 1, 140),
        ]
    )
    clauses = split_text_lines(lines)
    assert len(clauses) == 2
    assert "月付。" in clauses[0].text


def test_numbered_and_paren_patterns():
    lines = make_lines(
        [
            ("3.1 甲方负责维修。", 1, 100),
            ("（一）主体结构由甲方承担。", 1, 116),
            ("（二）日常损耗由乙方承担。", 1, 132),
        ]
    )
    clauses = split_text_lines(lines)
    assert clauses[0].clause_no == "3.1"
    assert clauses[1].clause_no == "（一）"
    assert clauses[2].clause_no == "（二）"


def test_empty_lines_returns_empty():
    assert split_text_lines([]) == []


def test_sub_items_stay_inside_article():
    """有"第X条"时，其下的（一）（二）（三）不另起条款，避免条被切碎。"""
    lines = make_lines(
        [
            ("第一条 房屋基本情况", 1, 100),
            ("（一）房屋坐落：某市某区某路 1 号。", 1, 116),
            ("（二）房屋状态：两室一厅。", 1, 132),
            ("第二条 租赁期限为一年。", 1, 160),
        ]
    )
    clauses = split_text_lines(lines)

    assert len(clauses) == 2
    assert clauses[0].clause_no == "第一条"
    assert "（二）房屋状态" in clauses[0].text
    assert clauses[1].clause_no == "第二条"
