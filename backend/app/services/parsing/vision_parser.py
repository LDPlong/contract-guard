"""图片合同解析：交给多模态模型直接读图，不走 OCR（文档 1.1 / 评分项「多模态能力」）。

为什么不用 PaddleOCR：
- 装不上（Windows + Python 3.13 兼容性差，包体近 1GB）
- 传统 OCR 只给文字，不给"第X条"的语义边界
多模态模型一次调用同时完成识别与结构化，且对拍照倾斜、表格线更宽容。

代价：没有坐标。图片合同只能走"条款视图"，不能做 bbox 高亮——这点在页面上要如实标注。
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger
from app.services.llm.client import LLMClient
from app.services.parsing.models import Clause

log = get_logger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_CLAUSES = 200

SYSTEM = """你是合同结构化助手。用户会给一张合同照片或扫描件，你要把内容整理成结构化 JSON。

【输出】只输出一个 JSON 对象，不要 markdown，不要解释：
{
  "contract_type": "lease|labor|prepaid|unknown",
  "clauses": [
    { "clause_no": "第一条", "text": "该条完整正文" }
  ]
}

【规则】
1. 按合同原有的"第X条"逐条输出；没有编号时按自然段落输出，clause_no 返回 null。
2. text 必须是图中真实存在的文字，不得改写、缩写、补全或编造。
3. 页眉页脚、签字栏、页码不要作为条款输出。
4. 看不清的字用「□」占位，不要猜。
5. 合同类型判断：出现出租人/承租人/押金判为 lease；用人单位/试用期判为 labor；
   课程/培训/贷款/退费判为 prepaid；都不明显则 unknown。
"""


@dataclass
class VisionResult:
    contract_type: str
    clauses: list[Clause] = field(default_factory=list)
    full_text: str = ""
    warnings: list[str] = field(default_factory=list)


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    raw = path.read_bytes()
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("图片超过 8MB，请压缩后重试")
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def _normalize(result: dict) -> VisionResult:
    raw_clauses = result.get("clauses")
    if not isinstance(raw_clauses, list):
        raise ValueError("模型未返回 clauses 数组")

    clauses: list[Clause] = []
    cursor = 0
    for item in raw_clauses[:MAX_CLAUSES]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if len(text) < 2:
            continue
        no = item.get("clause_no")
        clause_no = str(no).strip() if no else None
        clauses.append(
            Clause(
                seq=len(clauses) + 1,
                clause_no=clause_no,
                heading_kind=None,
                page_no=1,
                bbox=None,  # 图片没有坐标，前端只能做文本级高亮
                text=text,
                char_start=cursor,
                char_end=cursor + len(text),
            )
        )
        cursor += len(text) + 1

    if not clauses:
        raise ValueError("未从图片中识别出条款")

    return VisionResult(
        contract_type=str(result.get("contract_type") or "unknown"),
        clauses=clauses,
        full_text="\n".join(c.text for c in clauses),
        warnings=["图片合同不含坐标，仅支持条款级定位"],
    )


async def parse_image(
    path: str | Path,
    client: LLMClient | None = None,
) -> VisionResult:
    """图片 → 结构化条款。失败抛 ValueError，由上层转成 ParseFailed。"""
    image_path = Path(path)
    if not image_path.is_file():
        raise ValueError("图片文件不存在")

    llm = client or LLMClient()
    data_url = _data_url(image_path)

    result = await llm.chat_json_with_image(
        SYSTEM,
        "请识别这张合同图片并按约定 JSON 输出。",
        data_url,
        max_tokens=4096,
    )
    if not result.ok:
        raise ValueError("模型输出无法解析为约定 JSON")

    return _normalize(result.parsed or {})
