"""LLM 连通性与 JSON 契约冒烟脚本。

用法：
    python -m scripts.llm_smoke

会真实产生一次极小的模型调用（约 100 tokens），用于确认 .env 配置可用。
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.services.llm import LLMClient

SYSTEM = (
    "你是合同条款风险审查助手。只输出 JSON，不要 markdown，不要解释。"
    '字段：{"hit":bool,"risk_level":"high|medium|low|none","title":str,"confidence":0-1}'
)
CLAUSE = "乙方提前退租的，押金及剩余租金不予退还。"


async def main() -> None:
    settings = get_settings()
    print(f"provider={settings.llm_base_url} model={settings.llm_model}")
    client = LLMClient()

    greeting = await client.ping()
    print(f"ping -> {greeting}")

    result = await client.chat_json(SYSTEM, f"审查该条款：{CLAUSE}", max_tokens=200)
    print(f"latency={result.latency_ms}ms tokens={result.cost_tokens} attempts={result.attempts}")
    print("raw:", result.content.strip()[:200])

    if result.ok:
        print("parsed:", json.dumps(result.parsed, ensure_ascii=False))
    else:
        print("解析失败 —— 需要走人工复核兜底")


if __name__ == "__main__":
    asyncio.run(main())
