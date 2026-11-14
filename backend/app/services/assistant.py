"""内置法律答疑助手（v1.3 新增）。

定位：解释法条、名词和"这条为什么算风险"，不代理具体案件。
边界写死在提示词里，也在代码里做二次校验——
- 拒答：预测判决结果、代为起草合同条款、具体案件代理、与合同法律无关的提问
- 每条回答必须挂在本轮检索到的法条上；引用不在集合内的一律丢弃
- 检索为空就直说"没查到依据"，不靠模型自己的记忆答

为什么不做成多轮对话：一来多轮容易滑向"帮我看这个案子"，二来历史上下文会稀释法条约束。
这里只保留最近一问一答的语境，每一轮都重新检索、重新校验。
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from app.core.logging import get_logger
from app.services.llm.client import LLMClient
from app.services.rag.retriever import Retriever
from app.services.rag.types import RetrievedChunk

log = get_logger(__name__)

PROMPT_VERSION = "assist-1.0"

MAX_QUESTION_CHARS = 200
MAX_CONTEXT_CHARS = 400
MAX_ANSWER_CHARS = 700
TOP_K = 4
MAX_QUOTE_CHARS = 180

# 明显越界的提问，直接前置拦截，不浪费一次模型调用
_OUT_OF_SCOPE = (
    re.compile(r"(能|会|是否|能不能)(赢|胜诉|打赢|判我胜)"),
    re.compile(r"(预测|估计|大概).{0,6}(判决|结果|输赢)"),
    re.compile(r"(帮我|替我|给我)(写|起草|拟).{0,8}(条款|合同|协议|起诉状|律师函)"),
    re.compile(r"(你是|你算).{0,4}(律师|法律顾问)"),
)

# 口语 → 法条用词。用户问"押金"，民法典里只写"返还租赁物"，
# 直接拿口语去检索必然落空，这里做一层确定性桥接（不依赖模型改写，结论可复现）。
SYNONYMS: dict[str, str] = {
    "押金": "押金 保证金 返还租赁物 租赁期限届满",
    "退租": "提前解除 解除合同 剩余租金 返还租赁物",
    "转租": "转租 出租人同意 第三人",
    "涨租": "租金 变更合同 协商一致",
    "违约金": "违约金 过分高于造成的损失 适当减少",
    "定金": "定金 不得超过 主合同标的额",
    "试用期": "试用期 不得超过 六个月 同一用人单位",
    "社保": "社会保险 缴纳 用人单位",
    "加班": "延长工作时间 加班 工资报酬",
    "竞业限制": "竞业限制 经济补偿 二年",
    "离职": "解除劳动合同 提前三十日 经济补偿",
    "辞退": "解除劳动合同 严重违反规章制度 经济补偿",
    "退费": "退费 格式条款 排除对方主要权利",
    "概不退款": "格式条款 免除责任 排除对方主要权利 无效",
    "解释权": "格式条款 解释 不利于提供格式条款一方",
    "格式条款": "格式条款 提示说明义务 免除或者减轻其责任",
    "管辖": "协议管辖 书面协议 人民法院",
    "维修": "出租人应当履行租赁物的维修义务 承租人",
}

SYSTEM = """你是 ContractGuard 的内置法律答疑助手，面向没有法律背景的普通用户，
回答与合同、劳动、租房、预付式消费相关的问题。

【职责边界】
1. 你只做三件事：解释法条含义、解释法律名词、说明某类条款为什么有风险。
2. 以下请求一律不答，直接返回 scope_ok=false：
   - 预测诉讼或仲裁结果、评估胜诉概率
   - 代写合同条款、起诉状、律师函等法律文书
   - 代理具体案件、指导如何取证或对抗对方
   - 与合同法律无关的问题
3. 你不能声称自己是律师，不能给出"一定能赢""必然无效"这类确定结论。
4. 只依据下面提供的"法条依据"回答。不得引用未提供的法条，不得编造条号或内容。
5. used_chunk_ids 只能取自提供的法条列表；没有可用法条时返回空数组，
   并在 answer 里说明"现有法规库里没有直接对应的条文"。
6. 检索是按字面匹配的，可能夹带与问题无关的条文（例如问租赁却召回专利条款）。
   与问题无关的一律忽略，不要写进 used_chunk_ids，也不要为它硬凑解释。

【表达要求】
- 简体中文，口语化，不用法条腔。
- answer 控制在 300 字以内，先给结论，再说依据，最后给一句提醒。
- 不要输出 markdown 标题、表格、代码块。

【输出 JSON 结构】
{
  "scope_ok": boolean,       // 是否属于可回答范围
  "answer": string,          // 回答正文，不超过 300 字
  "used_chunk_ids": [string] // 实际依据的法条编号
}"""


def build_user(question: str, context: str, chunks: list[RetrievedChunk]) -> str:
    parts = [f"【用户问题】\n{question.strip()[:MAX_QUESTION_CHARS]}"]
    if context.strip():
        parts.append(f"【当前上下文】\n{context.strip()[:MAX_CONTEXT_CHARS]}")
    if chunks:
        laws = []
        for chunk in chunks:
            laws.append(
                f"- chunk_id={chunk.chunk_id}｜{chunk.source} {chunk.article_no}\n"
                f"  {chunk.content[:MAX_QUOTE_CHARS]}"
            )
        parts.append("【法条依据】\n" + "\n".join(laws))
    else:
        parts.append("【法条依据】\n（本轮没有检索到相关法条）")
    return "\n\n".join(parts)


def expand_query(question: str) -> list[str]:
    """原问题 + 命中的口语词扩展，两路分别检索后合并。"""
    extras: list[str] = []
    for term, expansion in SYNONYMS.items():
        if term in question:
            extras.append(expansion)
    if not extras:
        return [question]
    return [question, " ".join(dict.fromkeys(" ".join(extras).split()))]


async def _search(retriever: Retriever, question: str) -> list[RetrievedChunk]:
    """多路检索后按 chunk 去重，保留最高分，再按分数排序。"""
    merged: dict[str, RetrievedChunk] = {}
    for query in expand_query(question):
        try:
            found = await retriever.search(query, top_k=TOP_K)
        except Exception:
            log.exception("assistant retrieve failed query_len=%s", len(query))
            continue
        for chunk in found:
            current = merged.get(chunk.chunk_id)
            if current is None or chunk.score > current.score:
                merged[chunk.chunk_id] = chunk
    return sorted(merged.values(), key=lambda c: c.score, reverse=True)[:TOP_K]


def looks_out_of_scope(question: str) -> bool:
    """前置拦截：明显越界的提问不调模型。"""
    return any(pattern.search(question) for pattern in _OUT_OF_SCOPE)


def _clean_answer(text: str) -> str:
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = re.sub(r"[ \t]+", " ", text)
    return text[:MAX_ANSWER_CHARS]


REFUSAL = (
    "这个问题超出了我的范围。我能做的是解释法条和名词、说明某类条款为什么有风险；"
    "判断能不能赢、替你写条款、或者代理具体纠纷，需要执业律师。"
)
NO_LAW = (
    "现有法规库里没有检索到直接对应的条文，我不做没有依据的推测。"
    "可以换个说法再问一次，或者去法规库按关键词翻一翻。"
)


async def stream_answer(
    *,
    question: str,
    context: str = "",
    retriever: Retriever | None = None,
    client: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """产出一轮答疑的 SSE 事件：refs → answer → done。"""
    question = question.strip()[:MAX_QUESTION_CHARS]
    if not question:
        yield {"event": "answer", "data": {"answer": "请先输入问题。", "refs": [], "scope_ok": True}}
        return

    if looks_out_of_scope(question):
        log.info("assistant refused by rule, len=%s", len(question))
        yield {
            "event": "answer",
            "data": {"answer": REFUSAL, "refs": [], "scope_ok": False, "reason": "rule"},
        }
        return

    retriever = retriever or Retriever()
    client = client or LLMClient()

    chunks = await _search(retriever, question)

    # 依据先推给前端，用户不用等模型就能看到"手上有哪几条法"
    yield {"event": "refs", "data": {"refs": [c.as_dict() for c in chunks]}}

    if not chunks:
        yield {
            "event": "answer",
            "data": {"answer": NO_LAW, "refs": [], "scope_ok": True, "reason": "retrieve_empty"},
        }
        return

    try:
        result = await client.chat_json(SYSTEM, build_user(question, context, chunks), max_tokens=800)
    except Exception:
        log.exception("assistant llm failed")
        yield {
            "event": "answer",
            "data": {
                "answer": "模型暂时没能返回结果，可以稍后再问一次。",
                "refs": [c.as_dict() for c in chunks],
                "scope_ok": True,
                "reason": "llm_failed",
                "needs_review": True,
            },
        }
        return

    parsed = result.parsed or {}
    allowed = {c.chunk_id: c for c in chunks}
    used = [cid for cid in parsed.get("used_chunk_ids", []) if cid in allowed]
    answer = _clean_answer(str(parsed.get("answer", ""))) or NO_LAW
    scope_ok = bool(parsed.get("scope_ok", True))

    # 模型说"不在这轮法条里"但给了 used，说明引用不可信，退回无依据表述
    if used and not scope_ok:
        used = []

    yield {
        "event": "answer",
        "data": {
            "answer": answer,
            "scope_ok": scope_ok,
            "refs": [allowed[cid].as_dict() for cid in used],
            "prompt_version": PROMPT_VERSION,
            "model": result.model,
        },
    }
