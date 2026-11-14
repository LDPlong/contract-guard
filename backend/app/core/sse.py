"""SSE 帧格式化（审查流与答疑流共用）。

data 内不允许出现裸换行，否则前端按 \n\n 切帧会切错——统一在 json.dumps 里压成单行。
"""

from __future__ import annotations

import json


def sse_frame(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
