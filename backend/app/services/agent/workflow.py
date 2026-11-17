"""审查工作流：plan → gate → retrieve/judge → aggregate（文档 10 节）。

以异步生成器形式产出 SSE 事件，前端可以逐步渲染；持久化由 review_service 负责。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.core.constants import (
    JUDGE_TIMEOUT_SEC,
    MIN_LEGAL_BASIS_CHUNKS,
    Priority,
    RiskLevel,
)
from app.core.logging import get_logger
from app.services.agent.checklist import Checklist, ChecklistItem, load_checklist
from app.services.agent.framework import open_question_of, review_framework, stance_of
from app.services.agent.gating import Candidate, Gate
from app.services.agent.prompts import PROMPT_VERSION, SYSTEM, build_user
from app.services.agent.tools import (
    calc_safety_score,
    check_missing,
    is_blank_template,
    risk_levels_of,
)
from app.services.llm.client import LLMClient
from app.services.parsing.models import Clause
from app.services.rag.retriever import get_retriever

log = get_logger(__name__)

MAX_CONCURRENT_JUDGE = 3
CONTRACT_LABEL = {
    "lease": "房屋租赁",
    "labor": "劳动",
    "prepaid": "培训贷 / 预付卡",
}
LEGAL_QUOTE_CHARS = 80
PROMPT_LAW_TOP = 5  # 塞进提示词的法条条数上限（参考法条优先占位）
VALID_LEVELS = {RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW, RiskLevel.NONE}

# 涉及法定权利、已付款项或退出权的，即使只是中风险也列入"必守"。
MUST_KEYWORDS = (
    "押金", "保证金", "社保", "工资", "违约金", "解除", "终止", "退款", "退费",
    "放弃", "无效", "试用期", "竞业", "必备条款", "退出权不对等", "虚假前提",
)
IMPACT_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("押金", "保证金", "预付款"), "可能损失已支付的押金 / 预付款"),
    (("违约金", "赔偿", "扣款"), "可能被要求支付额外费用或承担赔偿"),
    (("解除", "终止", "退租", "退款", "退费"), "可能难以中途退出，或已付费用拿不回来"),
    (("社保", "保险"), "可能影响社保待遇与后续维权"),
    (("工资", "薪酬", "试用期", "加班"), "可能直接影响实际到手收入"),
    (("竞业", "保密"), "可能影响离职后的就业范围"),
    (("必备条款", "主体", "期限"), "关键要素不清，发生争议时难以举证"),
    (("义务单向性", "违约对称性"), "出问题时可能缺少可主张的依据"),
    (("虚假前提", "格式条款"), "可能预先放弃了本可以主张的权利"),
)


def _priority_of(level: str, text: str) -> str:
    """谈判优先级由代码定，不交给模型——只给沟通次序，不产出条文。"""
    if level == RiskLevel.HIGH:
        return Priority.MUST
    if level == RiskLevel.MEDIUM:
        return Priority.MUST if any(k in text for k in MUST_KEYWORDS) else Priority.NEGOTIABLE
    return Priority.YIELDABLE


def _impact_of(level: str, text: str) -> str:
    if level == RiskLevel.NONE:
        return "该项未完成自动判定，影响暂无法评估"
    for keywords, sentence in IMPACT_RULES:
        if any(k in text for k in keywords):
            return sentence
    return "可能增加履约成本，或让后续维权更被动"


def _presentation(level: str, category: str, title: str, reason: str = "") -> tuple[str, str]:
    text = f"{category}{title}{reason}"
    return _priority_of(level, text), _impact_of(level, text)


@dataclass
class FindingDraft:
    item_id: str
    category: str
    risk_level: str
    title: str
    reason: str
    suggestion: str
    legal_basis: list[dict] = field(default_factory=list)
    negotiation_tip: str | None = None
    confidence: float = 0.0
    clause_id: str | None = None      # 条款 key（c{seq}），落库时映射为数据库 id
    clause_seq: int | None = None
    clause_no: str | None = None
    page_no: int | None = None
    needs_review: bool = False
    priority: str = Priority.YIELDABLE
    impact: str = ""

    def as_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "category": self.category,
            "risk_level": self.risk_level,
            "title": self.title,
            "reason": self.reason,
            "legal_basis": self.legal_basis,
            "suggestion": self.suggestion,
            "negotiation_tip": self.negotiation_tip,
            "confidence": round(self.confidence, 3),
            "clause_id": self.clause_id,
            "clause_seq": self.clause_seq,
            "clause_no": self.clause_no,
            "page_no": self.page_no,
            "needs_review": self.needs_review,
            "priority": self.priority,
            "impact": self.impact,
        }


def _clause_key(clause: Clause) -> str:
    """切分产物没有数据库 id，用 c{seq} 作为工作流内部 key，落库时再映射。"""
    return getattr(clause, "id", "") or f"c{clause.seq}"


def _fallback_finding(item: ChecklistItem, reason: str) -> FindingDraft:
    """模型失败或输出不可用时的兜底：不编结论，标记需人工复核。"""
    priority, impact = _presentation(RiskLevel.NONE, item.category, item.name)
    return FindingDraft(
        item_id=item.id,
        category=item.category,
        risk_level=RiskLevel.NONE,
        title=f"{item.name}：自动判定未完成",
        reason=reason,
        suggestion="该项需人工复核。",
        confidence=0.0,
        needs_review=True,
        priority=priority,
        impact=impact,
    )


def _uncovered_finding(item: ChecklistItem) -> FindingDraft:
    """依据充分性闸门：零法条命中时不让模型下结论（文档硬约束 5）。

    与"模型调用失败"分开，是为了让复核的人一眼看出该补的是法条还是重试。
    """
    priority, impact = _presentation(RiskLevel.NONE, item.category, item.name)
    return FindingDraft(
        item_id=item.id,
        category=item.category,
        risk_level=RiskLevel.NONE,
        title=f"{item.name}：依据不足，未下结论",
        reason="该审查项没有检索到可直接引用的法条，也没有命中清单里人工校过的参考法条；"
        "为避免凭空判断，本项不做自动判定。",
        suggestion="请人工核对该条款，或补充对应的法规语料后重新审查。",
        confidence=0.0,
        needs_review=True,
        priority=priority,
        impact=impact,
    )


_ARTICLE_IN_TEXT = __import__("re").compile(r"第([一二三四五六七八九十百零〇]+)条")


def _pick_primary(candidates: list[Candidate], payload: dict) -> Candidate | None:
    """模型不会返回 clause_id，所以从它自己的表述里反推是哪一条。

    顺序：① 理由里点名了"第X条"且命中候选 → ② 与理由文字重合度最高的候选 → ③ 预筛第一名
    """
    if not candidates:
        return None
    text = f"{payload.get('title', '')}{payload.get('reason', '')}"

    for match in _ARTICLE_IN_TEXT.finditer(text):
        target = f"第{match.group(1)}条"
        for cand in candidates:
            if cand.clause.clause_no == target:
                return cand

    best, best_hits = candidates[0], -1
    for cand in candidates:
        hits = sum(1 for kw in (cand.keyword_hits or []) if kw in text)
        hits += sum(1 for ch in set(text) if ch in cand.clause.text)
        if hits > best_hits:
            best, best_hits = cand, hits

    # 前置说明/目录段落没有条号，挂上去会导致"点结论定位不到原文"
    if best.clause.clause_no is None:
        named = [c for c in candidates if c.clause.clause_no]
        if named:
            return max(named, key=lambda c: c.score)
    return best


def _to_finding(
    item: ChecklistItem,
    payload: dict,
    primary: Candidate | None,
    valid_chunk_ids: set[str],
) -> FindingDraft:
    level = str(payload.get("risk_level", RiskLevel.NONE)).lower()
    if level not in VALID_LEVELS:
        level = RiskLevel.NONE

    basis: list[dict] = []
    for entry in payload.get("legal_basis") or []:
        if not isinstance(entry, dict):
            continue
        chunk_id = str(entry.get("chunk_id", ""))
        # 只保留检索命中的 chunk，防止模型编造引用
        if chunk_id and chunk_id in valid_chunk_ids:
            basis.append(
                {
                    "source": str(entry.get("source", ""))[:40],
                    "article": str(entry.get("article", ""))[:32],
                    "quote": str(entry.get("quote", ""))[:LEGAL_QUOTE_CHARS],
                    "chunk_id": chunk_id,
                }
            )

    confidence = float(payload.get("confidence") or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    if not basis:
        confidence = min(confidence, 0.5)  # 无依据的结论不给高置信度

    category = str(payload.get("category") or item.category)[:16]
    title = str(payload.get("title") or item.name)[:30]
    reason = str(payload.get("reason") or "")[:200]
    priority, impact = _presentation(level, category, title, reason)

    return FindingDraft(
        item_id=item.id,
        category=category,
        risk_level=level,
        title=title,
        reason=reason,
        suggestion=str(payload.get("suggestion") or "")[:300],
        legal_basis=basis,
        negotiation_tip=(
            str(payload.get("negotiation_tip"))[:150]
            if payload.get("negotiation_tip")
            else None
        ),
        confidence=confidence,
        clause_id=_clause_key(primary.clause) if primary else None,
        clause_seq=primary.clause.seq if primary else None,
        clause_no=primary.clause.clause_no if primary else None,
        page_no=primary.clause.page_no if primary else None,
        priority=priority,
        impact=impact,
    )


async def _judge_item(
    item: ChecklistItem,
    candidates: list[Candidate],
    missing: list[str],
    full_text: str,
    retriever: Retriever,
    client: LLMClient,
) -> FindingDraft:
    if item.mode == "missing_check":
        if not missing:
            return _fallback_hit_none(item)
        chunks = retriever.resolve_refs(item.legal_refs)[:1] or await retriever.search(
            item.query, top_k=1
        )
        basis = [
            {
                "source": c.source,
                "article": c.article_no,
                "quote": c.content[:LEGAL_QUOTE_CHARS],
                "chunk_id": c.chunk_id,
            }
            for c in chunks
        ]
        # missing_check 的结论来自"合同里缺哪个词"的文本规则，不依赖法条推理，
        # 因此即使法条通道为空也照常提示，但只作缺项提示、不附法条结论。
        title = f"合同缺少{('、'.join(missing))[:20]}"[:30]
        reason = f"未在合同中找到以下必备要素：{'、'.join(missing)}。"
        priority, impact = _presentation(item.weight, item.category, title, reason)
        return FindingDraft(
            item_id=item.id,
            category=item.category,
            risk_level=item.weight,
            title=title,
            reason=reason,
            suggestion="建议补充上述必备要素，明确金额、期限与履行方式后再签署。",
            legal_basis=basis,
            negotiation_tip="这几项是合同的基本内容，补上对双方都清楚。",
            confidence=0.8,
            page_no=None,
            priority=priority,
            impact=impact,
        )

    if not candidates:
        return _fallback_hit_none(item)

    # 参考法条优先：清单里点名的那几条按条精确取，检索只做补充
    pinned = retriever.resolve_refs(item.legal_refs)
    try:
        retrieved = await retriever.search(item.query, top_k=PROMPT_LAW_TOP)
    except Exception:  # noqa: BLE001
        retrieved = []
    pinned_ids = {c.chunk_id for c in pinned}
    chunks = (pinned + [c for c in retrieved if c.chunk_id not in pinned_ids])[:PROMPT_LAW_TOP]

    # 依据充分性闸门：零条直接相关法条时不下结论。
    # 清单里的 legal_refs 是人工校过的精确通道，一条即可；语义检索只是补充。
    # 之前这里无论命中几条都照样调模型，只靠压低 confidence 兜底，仍会产出"没依据的结论"。
    if len(chunks) < MIN_LEGAL_BASIS_CHUNKS:
        log.info("legal basis insufficient item=%s hits=%d", item.id, len(chunks))
        return _uncovered_finding(item)

    clause_list = [c.clause for c in candidates]
    user_prompt = build_user(item, clause_list, chunks)
    valid_ids = {c.chunk_id for c in chunks}

    try:
        result = await asyncio.wait_for(
            client.chat_json(SYSTEM, user_prompt, max_tokens=800),
            timeout=JUDGE_TIMEOUT_SEC,
        )
    except Exception as exc:  # noqa: BLE001  超时与网络错误都走兜底
        log.warning("judge failed item=%s err=%s", item.id, type(exc).__name__)
        return _fallback_finding(item, "模型调用超时或失败，该项未完成判定。")

    if not result.ok:
        return _fallback_finding(item, "模型输出无法解析为约定 JSON，该项未完成判定。")

    payload = result.parsed or {}
    return _to_finding(item, payload, _pick_primary(candidates, payload), valid_ids)


def _fallback_hit_none(item: ChecklistItem) -> FindingDraft:
    title = f"未发现{item.name}相关风险"
    priority, impact = _presentation(RiskLevel.NONE, item.category, title)
    return FindingDraft(
        item_id=item.id,
        category=item.category,
        risk_level=RiskLevel.NONE,
        title=title,
        reason="合同中未匹配到与该审查项相关的条款，或条款表述符合常规。",
        suggestion="无需修改。",
        confidence=0.7,
        priority=priority,
        impact=impact,
    )


def _soften_blank_template(findings: list[FindingDraft]) -> list[FindingDraft]:
    """空白模板里的"未约定"类结论不成立——那只是还没填。

    只降中风险，高风险不动：绝对化表述（概不退款、放弃社保）即使是模板也仍然是风险。
    """
    for finding in findings:
        if finding.risk_level != RiskLevel.MEDIUM:
            continue
        finding.risk_level = RiskLevel.LOW
        finding.needs_review = True
        finding.reason += "（该条款为空白待填项，最终风险取决于实际填写内容）"
    return findings


def _dedupe(findings: list[FindingDraft]) -> list[FindingDraft]:
    """同一份合同的同一处条款，同一类别只保留最严重的一条。"""
    order = {RiskLevel.HIGH: 3, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 1, RiskLevel.NONE: 0}
    best: dict[tuple, FindingDraft] = {}
    for finding in findings:
        if finding.risk_level == RiskLevel.NONE and not finding.needs_review:
            continue
        key = (finding.clause_id or finding.item_id, finding.category)
        current = best.get(key)
        if current is None or order[finding.risk_level] > order[current.risk_level]:
            best[key] = finding
    return sorted(best.values(), key=lambda f: order[f.risk_level], reverse=True)


def _build_summary(
    findings: list[FindingDraft], score: int, needs_review: int, blank_template: bool = False
) -> str:
    high = sum(1 for f in findings if f.risk_level == RiskLevel.HIGH)
    medium = sum(1 for f in findings if f.risk_level == RiskLevel.MEDIUM)
    low = sum(1 for f in findings if f.risk_level == RiskLevel.LOW)
    parts = [f"安全分 {score}/100"]
    parts.append(f"高风险 {high} 处、中风险 {medium} 处、低风险 {low} 处")
    if blank_template and needs_review:
        parts.insert(1, "本文件是未填写的合同模板")
        parts.append(f"另有 {needs_review} 项为空白待填项，签署前建议核对实际填写内容")
    elif needs_review:
        parts.append(f"另有 {needs_review} 项未能自动判定，建议人工复核")
    return "；".join(parts) + "。"


async def run_review(
    *,
    clauses: list[Clause],
    full_text: str,
    contract_type: str,
    checklist: Checklist | None = None,
    retriever: Retriever | None = None,
    client: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """执行一次完整审查，逐条产出 SSE 事件。"""
    board = checklist or load_checklist(contract_type)
    retriever = retriever or get_retriever()
    client = client or LLMClient()

    yield {
        "event": "step",
        "data": {
            "step": "plan",
            "status": "running",
            "message": (
                f"已识别为{CONTRACT_LABEL.get(board.contract_type, '')}合同，"
                f"共 {len(board)} 项需要核对"
            ),
        },
    }

    gate = Gate(clauses)
    plan: list[tuple[ChecklistItem, list[Candidate], list[str]]] = []
    skipped: list[str] = []
    for item in board.items:
        missing = (
            check_missing(full_text, item.required_terms) if item.mode == "missing_check" else []
        )
        candidates = gate.candidates(item)
        if candidates or missing:
            plan.append((item, candidates, missing))
        else:
            skipped.append(item.id)

    yield {
        "event": "step",
        "data": {
            "step": "gate",
            "status": "done",
            "message": (
                f"从 {len(clauses)} 条条款中匹配到 {len(plan)} 处需要核对"
                + (f"，{len(skipped)} 项不涉及" if skipped else "")
            ),
            "skipped_items": skipped,
        },
    }

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_JUDGE)
    total = len(plan)
    done = 0
    results: list[FindingDraft] = []

    async def guarded(item, candidates, missing):
        async with semaphore:
            return await _judge_item(item, candidates, missing, full_text, retriever, client)

    tasks = [asyncio.create_task(guarded(*entry)) for entry in plan]
    try:
        for task in asyncio.as_completed(tasks):
            finding = await task
            done += 1
            results.append(finding)
            if finding.risk_level != RiskLevel.NONE:
                yield {"event": "finding", "data": finding.as_dict()}
            yield {"event": "progress", "data": {"done": done, "total": total}}
    finally:
        # 客户端断开会 cancel 生成器：未完成的判定任务必须显式取消，
        # 否则它们作为孤儿继续跑完，白烧几十次模型调用
        for task in tasks:
            if not task.done():
                task.cancel()

    # 框架审阅：清单逐条判定看不到的"整份合同一边倒"，纯规则、零模型调用。
    # 放在聚合阶段产出，命中一律提示级（low），不当成确证风险。
    framework_observations = review_framework(clauses)
    for obs in framework_observations:
        evidence = next((c for c in clauses if c.seq == obs["clause_seq"]), None)
        impact = _impact_of(RiskLevel.LOW, f"{obs['category']}{obs['title']}{obs['reason']}")
        results.append(
            FindingDraft(
                item_id=obs["item_id"],
                category=obs["category"],
                risk_level=RiskLevel.LOW,
                title=obs["title"],
                reason=obs["reason"],
                suggestion=obs["suggestion"],
                negotiation_tip=obs["negotiation_tip"],
                confidence=0.6,
                clause_id=_clause_key(evidence) if evidence else None,
                clause_seq=evidence.seq if evidence else None,
                clause_no=evidence.clause_no if evidence else None,
                page_no=evidence.page_no if evidence else None,
                priority=obs["priority"],
                impact=impact,
            )
        )

    blank_template = is_blank_template(clauses)
    if blank_template:
        results = _soften_blank_template(results)
    findings = _dedupe(results)
    needs_review = sum(1 for f in results if f.needs_review)
    missing_count = sum(
        1
        for f in results
        if f.item_id
        and any(i.id == f.item_id and i.mode == "missing_check" for i in board.items)
        and f.risk_level != RiskLevel.NONE
    )
    score = calc_safety_score(risk_levels_of([f.as_dict() for f in results]), missing_count)

    yield {
        "event": "done",
        "data": {
            "safety_score": score,
            "summary": _build_summary(findings, score, needs_review, blank_template),
            "findings": [f.as_dict() for f in findings],
            "skipped_items": skipped,
            "needs_review": needs_review,
            "prompt_version": PROMPT_VERSION,
            "checklist_version": board.version,
            "blank_template": blank_template,
            # 立场声明与"清单之外的一个问题"：让用户知道结论站在哪一侧、
            # 以及 checklist 没有覆盖但会影响签字决策的盲区。
            "stance": stance_of(board.contract_type),
            "open_question": open_question_of(board.contract_type),
            "framework_flags": [
                {"key": obs["item_id"], "category": obs["category"], "title": obs["title"]}
                for obs in framework_observations
            ],
        },
    }
