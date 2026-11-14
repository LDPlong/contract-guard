"""内置答疑助手接口（v1.3）。

SSE 走 POST，事件序列：refs → answer。
refs 先到，用户能在等待模型时就看到本轮检索到的法条。
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.constants import ErrorCode
from app.core.errors import BizError
from app.core.sse import sse_frame
from app.services import assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=assistant.MAX_QUESTION_CHARS)
    context: str = Field(default="", max_length=assistant.MAX_CONTEXT_CHARS)


@router.post("/ask", summary="问一个合同法律问题（SSE）")
async def ask(payload: AskIn):
    question = payload.question.strip()
    if not question:
        raise BizError(ErrorCode.PARAM_INVALID, "问题不能为空")

    async def frames():
        async for event in assistant.stream_answer(question=question, context=payload.context):
            yield sse_frame(event["event"], event["data"])

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
