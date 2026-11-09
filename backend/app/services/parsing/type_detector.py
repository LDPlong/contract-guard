"""合同类型识别（文档 9.3）。

三级策略：用户指定 → 关键词打分 → LLM 兜底。
M1 只实现前两级；LLM 兜底依赖 models/client（M4 落地），
在此之前识别失败时返回 unknown，由接口层提示用户手动选择，不做猜测。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import SUPPORTED_CONTRACT_TYPES, ContractType

# 关键词权重：强特征词 3，一般特征词 2，弱相关 1
KEYWORDS: dict[str, dict[str, int]] = {
    ContractType.LEASE: {
        "出租人": 3,
        "承租人": 3,
        "押金": 3,
        "租金": 3,
        "租赁": 3,
        "房屋": 2,
        "退租": 2,
        "转租": 2,
        "房东": 2,
        "房客": 2,
        "物业费": 1,
        "水电费": 1,
    },
    ContractType.LABOR: {
        "用人单位": 3,
        "劳动者": 3,
        "试用期": 3,
        "劳动合同": 3,
        "竞业限制": 3,
        "工资": 2,
        "社保": 2,
        "社会保险": 2,
        "加班": 2,
        "入职": 2,
        "岗位": 1,
        "考勤": 1,
    },
    ContractType.PREPAID: {
        "培训": 3,
        "贷款": 3,
        "退费": 3,
        "预付": 3,
        "课程": 2,
        "学员": 2,
        "机构": 2,
        "分期": 2,
        "课时": 2,
        "概不退款": 3,
        "借款": 2,
    },
}

MIN_SCORE = 3.0
MIN_MARGIN = 2.0
MAX_COUNT_PER_KEYWORD = 3  # 同一关键词最多计 3 次，避免重复堆分


@dataclass
class DetectionResult:
    contract_type: str
    source: str  # user | rule | llm | unknown
    scores: dict[str, float]

    @property
    def confident(self) -> bool:
        return self.contract_type in SUPPORTED_CONTRACT_TYPES


def _score_text(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for contract_type, keyword_map in KEYWORDS.items():
        total = 0.0
        for word, weight in keyword_map.items():
            count = min(text.count(word), MAX_COUNT_PER_KEYWORD)
            total += count * weight
        scores[contract_type] = total
    return scores


def detect_by_rules(text: str) -> DetectionResult:
    """关键词打分：最高分需同时满足阈值与领先幅度，否则判定为 unknown。"""
    scores = _score_text(text)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return DetectionResult(ContractType.UNKNOWN, "unknown", scores)

    best_type, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    if best_score >= MIN_SCORE and (best_score - runner_up) >= MIN_MARGIN:
        return DetectionResult(best_type, "rule", scores)
    return DetectionResult(ContractType.UNKNOWN, "unknown", scores)


def detect(
    text: str,
    user_choice: str | None = None,
    llm_classifier=None,
) -> DetectionResult:
    """三级识别入口。

    Args:
        text: 合同全文。
        user_choice: 用户显式指定，命中支持列表则直接采用。
        llm_classifier: 可选，签名 (text) -> str | None，M4 接入。
    """
    if user_choice in SUPPORTED_CONTRACT_TYPES:
        return DetectionResult(user_choice, "user", {})

    result = detect_by_rules(text)
    if result.confident:
        return result

    if llm_classifier is not None:
        guess = llm_classifier(text[:800])
        if guess in SUPPORTED_CONTRACT_TYPES:
            return DetectionResult(guess, "llm", result.scores)

    return DetectionResult(ContractType.UNKNOWN, "unknown", result.scores)
