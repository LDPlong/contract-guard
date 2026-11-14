"""Agent 工具：缺失条款检测与安全分计算（文档 10.2）。

评分必须由代码算，不交给模型——这是可复现性的底线。
"""

from __future__ import annotations

import re

from app.core.constants import (
    SCORE_BASE,
    SCORE_DEDUCT,
    SCORE_MAX,
    SCORE_MIN,
    SCORE_MISSING_ITEM_DEDUCT,
    RiskLevel,
)

# 合同的"填空位"：勾选框、方括号、下划线、以及"第＿种/第＿条"这类待选填编号。
# 正常的横排中文不会出现这些形态，因此命中即说明该处尚未填写。
FILL_BLANK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[\[\［]\s*[\]\］]"),
    re.compile(r"□"),
    re.compile(r"[＿_]{2,}"),
    re.compile(r"第[ \u3000]{1,3}[种条项]"),
)
# 平均每条条款的填空标记数达到该阈值，判定为"未填写的合同模板"。
# 实测：省级以上示范文本 4.8~4.9，已填写的合同 0.5 以下。
BLANK_TEMPLATE_DENSITY = 2.0


def count_fill_blanks(clauses) -> int:
    return sum(len(p.findall(c.text)) for c in clauses for p in FILL_BLANK_PATTERNS)


def is_blank_template(clauses) -> bool:
    """是否为未填写的空白模板。空白模板不应做"未约定"类风险定性。"""
    if not clauses:
        return False
    return count_fill_blanks(clauses) / len(clauses) >= BLANK_TEMPLATE_DENSITY


def calc_safety_score(risk_levels: list[str], missing_items: int = 0) -> int:
    """基础分 100，high 扣 12、medium 扣 5、low 扣 2，缺失必备条款每项扣 8。"""
    score = SCORE_BASE
    for level in risk_levels:
        score -= SCORE_DEDUCT.get(level, 0)
    score -= missing_items * SCORE_MISSING_ITEM_DEDUCT
    return max(SCORE_MIN, min(SCORE_MAX, score))


def check_missing(full_text: str, required_terms: list[str]) -> list[str]:
    """检测必备要素是否出现，返回缺失项。

    支持用 "|" 写同义写法：租赁合同里"房屋地址"可能写作"地址"，也可能写作"房屋坐落于"，
    只按字面匹配会把写清楚的合同判成缺项。
    """
    missing: list[str] = []
    for term in required_terms:
        alternatives = [part for part in term.split("|") if part]
        if not any(alt in full_text for alt in alternatives):
            missing.append(alternatives[0] if alternatives else term)
    return missing


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
