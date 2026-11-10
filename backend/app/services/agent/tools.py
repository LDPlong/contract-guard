"""Agent 工具：缺失条款检测与安全分计算（文档 10.2）。

评分必须由代码算，不交给模型——这是可复现性的底线。
"""

from __future__ import annotations

from app.core.constants import (
    SCORE_BASE,
    SCORE_DEDUCT,
    SCORE_MAX,
    SCORE_MIN,
    SCORE_MISSING_ITEM_DEDUCT,
    RiskLevel,
)


def calc_safety_score(risk_levels: list[str], missing_items: int = 0) -> int:
    """基础分 100，high 扣 12、medium 扣 5、low 扣 2，缺失必备条款每项扣 8。"""
    score = SCORE_BASE
    for level in risk_levels:
        score -= SCORE_DEDUCT.get(level, 0)
    score -= missing_items * SCORE_MISSING_ITEM_DEDUCT
    return max(SCORE_MIN, min(SCORE_MAX, score))


def check_missing(full_text: str, required_terms: list[str]) -> list[str]:
    """检测必备要素是否出现，返回缺失项。"""
    return [term for term in required_terms if term not in full_text]


def risk_levels_of(findings: list[dict]) -> list[str]:
    """取需要扣分的风险等级。

    注意：不能依赖 "hit" 字段——工作流产出的是 FindingDraft.as_dict()，里面没有 hit，
    只按 risk_level 是否为 none 判断（这里踩过一次，导致评分恒为 100）。
    """
    return [
        level
        for f in findings
        if (level := str(f.get("risk_level", RiskLevel.NONE))) != RiskLevel.NONE
    ]
