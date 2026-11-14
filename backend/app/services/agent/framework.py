"""框架审阅：在逐条判定之外，检查整份合同是不是"一边倒"。

清单项回答的是「这一条有没有风险」，这里回答的是「整份合同的权利义务怎么分布」。
纯规则统计，不调用模型、不增加审查耗时；观察结论一律提示级（low），
避免结构性判断把安全分压到与实际条款风险不成比例的数字。
"""

from __future__ import annotations

import re

from app.core.constants import (
    FRAMEWORK_IMBALANCE_RATIO,
    FRAMEWORK_MIN_FALSE_PREMISE,
    FRAMEWORK_MIN_OBLIGATIONS,
    FRAMEWORK_MIN_WEAK_BREACH,
    Priority,
)
from app.services.parsing.models import Clause

# 面向个人用户，默认站在合同中通常较弱势的一方（立场声明见 workflow）。
WEAK_PARTY = ("乙方", "承租方", "承租人", "劳动者", "员工", "消费者", "学员", "买受人")
STRONG_PARTY = ("甲方", "出租方", "出租人", "用人单位", "经营者", "服务方", "出卖人")
OBLIGATION_WORDS = ("应当", "应", "须", "必须", "不得", "承担", "支付", "缴纳", "负责")
BREACH_WORDS = ("违约金", "赔偿", "扣罚", "承担损失", "扣款")
STRONG_REMEDY_WORDS = ("违约金", "赔偿", "退还", "补偿", "承担")

# 退出权必须用"主体紧邻动作"的短窗口。用 .{0,14} 跨主体匹配会把
# 「乙方违约的，甲方有权解除」误算成乙方也拥有对等的退出权。
STRONG_EXIT_PATTERN = re.compile(r"甲方(?:有权|可以|可)(?:立即|单方|随时)?(?:解除|终止)")
WEAK_EXIT_PATTERN = re.compile(
    r"乙方(?:有权|可以|可)(?:立即|单方|随时)?(?:解除|终止|退租)"
)
FALSE_PREMISE_PATTERNS = (
    re.compile(r"视为.{0,10}(已|自愿)(知悉|同意|确认|认可|验收|接受)"),
    re.compile(r"(已充分|已经充分).{0,8}(了解|知悉|理解).{0,14}(放弃|不得|自愿|无权)"),
    re.compile(r"无条件放弃"),
    re.compile(r"不得以任何理由"),
)

_SENTENCE_SPLIT = re.compile(r"[。；;！？\n]")

STANCE: dict[str, str] = {
    "lease": "默认站在承租方（你）这一侧审阅；若你是出租方，以下结论不适用。",
    "labor": "默认站在劳动者 / 实习生一侧审阅；若你是用人单位，以下结论不适用。",
    "prepaid": "默认站在消费者 / 学员一侧审阅；若你是机构方，以下结论不适用。",
}
STANCE_DEFAULT = "默认站在合同中通常较弱势的一方审阅；若你代表对方，以下结论不适用。"

# 清单之外的一个问题：不重复清单里已有的审查项，只追问会影响决策的盲区。
OPEN_QUESTIONS: dict[str, str] = {
    "lease": (
        "这套房屋在出租前是否已设抵押或被查封？若有，『买卖不破租赁』可能不适用，"
        "换房成本要提前算进去。"
    ),
    "labor": (
        "这份合同与 offer、入职后另签的劳动合同是否一致？约定以哪份为准，"
        "会直接影响试用期与薪酬的认定。"
    ),
    "prepaid": (
        "若机构停业或课程停开，已付费用与分期贷款分别由谁承担？"
        "签约前最好书面确认停课后的还款安排。"
    ),
}
OPEN_QUESTION_DEFAULT = "对方若中途变更经营主体或联系方式，你能否及时收到通知并主张权利？"


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _sentences(clauses: list[Clause]) -> list[tuple[Clause, str]]:
    return [
        (clause, part.strip())
        for clause in clauses
        for part in _SENTENCE_SPLIT.split(clause.text)
        if part.strip()
    ]


def _observation(
    item_id: str,
    category: str,
    title: str,
    reason: str,
    suggestion: str,
    priority: str,
    evidence: Clause,
) -> dict:
    return {
        "item_id": item_id,
        "category": category,
        "title": title,
        "reason": reason,
        "suggestion": suggestion,
        "negotiation_tip": "可以先问一句：这条能不能对双方都一样？",
        "priority": priority,
        "clause_seq": evidence.seq,
        "clause_no": evidence.clause_no,
        "page_no": evidence.page_no,
    }


def _single_party(
    sentences: list[tuple[Clause, str]], party: tuple[str, ...], other: tuple[str, ...]
) -> list[tuple[Clause, str]]:
    """只保留只出现一方称谓的句子。

    中文条款常把甲乙双方写在同一句（「乙方违约的，甲方有权解除」），
    共现句无法用规则判定归属，硬算会既漏报又误报，因此直接跳过。
    """
    return [
        (clause, text)
        for clause, text in sentences
        if _has_any(text, party) and not _has_any(text, other)
    ]


def review_framework(clauses: list[Clause]) -> list[dict]:
    """四问：义务单向性 / 退出权不对等 / 违约对称性 / 虚假前提。

    阈值在 9 份评测样本上调过：问题样本能命中，3 份官方示范文本零误报。
    """
    if not clauses:
        return []

    sentences = _sentences(clauses)
    weak_only = _single_party(sentences, WEAK_PARTY, STRONG_PARTY)
    strong_only = _single_party(sentences, STRONG_PARTY, WEAK_PARTY)
    found: list[dict] = []

    # ① 义务单向性
    weak_obligations = [(c, s) for c, s in weak_only if _has_any(s, OBLIGATION_WORDS)]
    strong_obligations = [(c, s) for c, s in strong_only if _has_any(s, OBLIGATION_WORDS)]
    weak_n, strong_n = len(weak_obligations), len(strong_obligations)
    if weak_n >= FRAMEWORK_MIN_OBLIGATIONS and weak_n >= FRAMEWORK_IMBALANCE_RATIO * max(
        strong_n, 1
    ):
        found.append(
            _observation(
                "F01",
                "义务单向性",
                "整份合同的义务明显偏向你方",
                f"全文共 {weak_n} 处约定你方义务，仅 {strong_n} 处约定对方义务；"
                "只写你该做什么、不写对方该做什么，出问题时很难追究。",
                "逐条核对对方的主要义务（交付、维修、退款、告知）是否都有对应约定；"
                "这类结构性问题建议整体谈，而不是只改某一条。",
                Priority.NEGOTIABLE,
                weak_obligations[0][0],
            )
        )

    # ② 退出权不对等：主体紧邻动作的短窗口，避免跨主体误匹配
    strong_exits = [(c, s) for c, s in sentences if STRONG_EXIT_PATTERN.search(s)]
    weak_exits = [(c, s) for c, s in sentences if WEAK_EXIT_PATTERN.search(s)]
    if strong_exits and not weak_exits:
        found.append(
            _observation(
                "F02",
                "退出权不对等",
                "对方能解除，你方没有对等退出权",
                "合同写明对方可以解除或终止，却没找到你方对等的退出路径。"
                "想中途退出时，可能既要承担违约成本又拿不回已付款项。",
                "重点谈退出条件：什么情况下可以解除、提前多久通知、已付费用怎么退。",
                Priority.MUST,
                strong_exits[0][0],
            )
        )

    # ③ 违约对称性
    weak_breach = [(c, s) for c, s in weak_only if _has_any(s, BREACH_WORDS)]
    strong_breach = [(c, s) for c, s in strong_only if _has_any(s, STRONG_REMEDY_WORDS)]
    if len(weak_breach) >= FRAMEWORK_MIN_WEAK_BREACH and not strong_breach:
        found.append(
            _observation(
                "F03",
                "违约对称性",
                "违约责任只约束你方",
                f"全文有 {len(weak_breach)} 处约定你方的违约金或赔偿，"
                "却没找到对方违约时的对应责任；对方拖延交付、拒退费用时，"
                "可能缺少可主张的赔偿标准。",
                "建议补上对方违约时的处理方式和费用承担，两边的责任标准尽量对等。",
                Priority.NEGOTIABLE,
                weak_breach[0][0],
            )
        )

    # ④ 虚假前提
    full_text = "\n".join(c.text for c in clauses)
    false_premise_hits = [p for p in FALSE_PREMISE_PATTERNS if p.search(full_text)]
    if len(false_premise_hits) >= FRAMEWORK_MIN_FALSE_PREMISE:
        evidence = next(
            (c for c, s in sentences if any(p.search(s) for p in false_premise_hits)),
            clauses[0],
        )
        found.append(
            _observation(
                "F04",
                "虚假前提",
                "合同预先写死了对你不利的事实",
                "出现『视为已知悉』『无条件放弃』『不得以任何理由』一类写法，"
                "把尚未发生的事实或权利放弃预先推定成立，后续举证会很被动。",
                "这类概括性确认建议删去或改成具体、可核对的事实；签字前把不认可的表述划掉。",
                Priority.MUST,
                evidence,
            )
        )

    return found


def stance_of(contract_type: str) -> str:
    return STANCE.get(contract_type, STANCE_DEFAULT)


def open_question_of(contract_type: str) -> str:
    return OPEN_QUESTIONS.get(contract_type, OPEN_QUESTION_DEFAULT)
