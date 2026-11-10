"""提示词模板（版本化）。

修改任何提示词都必须同步提升 PROMPT_VERSION，并写入 reviews.prompt_version，
否则历史结论无法复现。
"""

from __future__ import annotations

from app.services.agent.checklist import ChecklistItem
from app.services.parsing.models import Clause
from app.services.rag.types import RetrievedChunk

PROMPT_VERSION = "judge-1.1"

MAX_CLAUSE_CHARS = 400
MAX_LAW_CHARS = 300

SYSTEM = """你是合同条款风险审查助手，面向没有法律背景的个人用户。

【硬性要求】
1. 只输出一个 JSON 对象，不要 markdown 代码块，不要任何解释文字。
2. 只依据下面提供的"合同条款"和"法条依据"判断，不得引用未提供的法条，不得编造法条内容。
3. legal_basis 里的 chunk_id 必须来自提供的法条列表；
   如果法条列表为空，legal_basis 返回 []，且 confidence 不得高于 0.5。
4. 不得给出"胜诉率""一定有效""必然败诉"等确定性表述。
5. suggestion 只写"建议方向 + 常见做法"，
   不得输出可直接粘贴进合同的完整条文，不得使用"甲方应……乙方应……"这类正式条款句式。
6. 输出语言为简体中文。

【输出 JSON 结构】
{
  "hit": boolean,                  // 该条款是否构成风险
  "risk_level": "high|medium|low|none",
  "category": string,              // 风险类别，如 押金/违约金/解除权
  "title": string,                 // 一句话结论，不超过 30 字
  "reason": string,                // 为什么有风险，不超过 200 字
  "legal_basis": [{"source": string, "article": string, "quote": string, "chunk_id": string}],
  "suggestion": string,            // 修改方向，不超过 300 字
  "negotiation_tip": string,       // 一句可以直接说出口的沟通话术，不超过 150 字
  "confidence": number             // 0-1
}

【判定口径】
- high：可能造成直接经济损失，或使对方丧失核心权利（如押金一律不退、单方随时解除、违约金畸高）
- medium：权利义务明显失衡，但可通过协商修正
- low：表述不规范、缺少一般性约定，实际影响有限
- none：未发现该审查项对应的风险（hit 为 false）
"""


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def build_user(
    item: ChecklistItem,
    candidates: list[Clause],
    chunks: list[RetrievedChunk],
) -> str:
    clause_block = "\n".join(
        f"[{c.clause_no or f'第{c.seq}段'}]（第 {c.page_no} 页）{_clip(c.text, MAX_CLAUSE_CHARS)}"
        for c in candidates
    ) or "（未匹配到相关条款）"

    if chunks:
        law_block = "\n".join(
            f"[{chunk.chunk_id}] {chunk.source} {chunk.article_no}："
            f"{_clip(chunk.content, MAX_LAW_CHARS)}"
            for chunk in chunks
        )
    else:
        law_block = "（本次未检索到相关法条，legal_basis 必须返回空数组）"

    return f"""【审查项】{item.name}（{item.id}）
【风险规则】{item.risk_rule}
【参考法条】{", ".join(item.legal_refs) if item.legal_refs else "无"}

【合同条款】
{clause_block}

【法条依据】
{law_block}

请判断上述条款是否命中该风险规则，并按指定 JSON 结构输出。"""
