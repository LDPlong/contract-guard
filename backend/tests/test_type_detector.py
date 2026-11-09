"""合同类型识别测试。"""

from __future__ import annotations

from app.services.parsing.type_detector import detect, detect_by_rules

LEASE_TEXT = (
    "房屋租赁合同：出租人将位于某市某区的房屋出租给承租人，"
    "租金每月三千元，押金一个月租金，租赁期限一年，退租需提前三十日通知。"
)
LABOR_TEXT = (
    "劳动合同：用人单位与劳动者约定试用期三个月，"
    "工资按月发放，依法缴纳社会保险，竞业限制期限两年。"
)
PREPAID_TEXT = (
    "培训服务协议：学员报名参加课程，学费通过分期贷款支付，"
    "退费需扣除违约金，机构对已上课时概不退款。"
)


def test_detect_lease():
    result = detect_by_rules(LEASE_TEXT)
    assert result.contract_type == "lease"
    assert result.source == "rule"
    assert result.confident is True


def test_detect_labor():
    assert detect_by_rules(LABOR_TEXT).contract_type == "labor"


def test_detect_prepaid():
    assert detect_by_rules(PREPAID_TEXT).contract_type == "prepaid"


def test_ambiguous_text_returns_unknown():
    result = detect_by_rules("本合同一式两份，双方签字后生效。")
    assert result.contract_type == "unknown"
    assert result.confident is False


def test_user_choice_wins():
    result = detect(LEASE_TEXT, user_choice="labor")
    assert result.contract_type == "labor"
    assert result.source == "user"


def test_invalid_user_choice_falls_back_to_rules():
    result = detect(LEASE_TEXT, user_choice="sales")
    assert result.contract_type == "lease"
    assert result.source == "rule"


def test_llm_fallback_used_when_rules_fail():
    result = detect("双方签字后生效。", llm_classifier=lambda _t: "prepaid")
    assert result.contract_type == "prepaid"
    assert result.source == "llm"


def test_llm_fallback_rejects_unsupported_answer():
    result = detect("双方签字后生效。", llm_classifier=lambda _t: "sales")
    assert result.contract_type == "unknown"
