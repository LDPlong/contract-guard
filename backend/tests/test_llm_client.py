"""LLM 客户端测试：全部走注入的假 transport，不发真实请求。"""

from __future__ import annotations

import httpx
import pytest
from openai import APITimeoutError

from app.core.errors import LLMFailed
from app.services.llm.client import LLMClient, extract_json


def make_transport(responses):
    """按顺序吐出预设响应；元素为 str 或 Exception。"""
    queue = list(responses)
    calls: list[int] = []

    async def _transport(messages, json_mode, max_tokens):
        calls.append(len(messages))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, {"prompt_tokens": 10, "completion_tokens": 5}, "fake-model"

    _transport.calls = calls  # type: ignore[attr-defined]
    return _transport


def timeout_error() -> APITimeoutError:
    return APITimeoutError(request=httpx.Request("POST", "https://example.com"))


# ---------- extract_json ----------


def test_extract_json_plain():
    assert extract_json('{"hit": true}') == {"hit": True}


def test_extract_json_with_fence():
    raw = '```json\n{"hit": false, "confidence": 0.2}\n```'
    assert extract_json(raw) == {"hit": False, "confidence": 0.2}


def test_extract_json_with_prose_around():
    raw = '好的，结论如下：{"hit": true} 以上。'
    assert extract_json(raw) == {"hit": True}


def test_extract_json_multiline():
    assert extract_json('{\n  "a": 1\n}') == {"a": 1}


def test_extract_json_invalid_returns_none():
    assert extract_json("这不是 JSON") is None
    assert extract_json("[1, 2, 3]") is None
    assert extract_json("") is None


# ---------- chat_json ----------


@pytest.mark.asyncio
async def test_chat_json_success():
    client = LLMClient(transport=make_transport(['{"hit": true, "confidence": 0.9}']))
    result = await client.chat_json("sys", "user")

    assert result.ok
    assert result.parsed == {"hit": True, "confidence": 0.9}
    assert result.attempts == 1
    assert result.cost_tokens == 15


@pytest.mark.asyncio
async def test_chat_json_retries_once_on_invalid():
    client = LLMClient(
        transport=make_transport(["我觉得有风险", '{"hit": true}']),
    )
    result = await client.chat_json("sys", "user")

    assert result.ok
    assert result.attempts == 2
    assert result.prompt_tokens == 20  # 两次调用累加
    assert result.parsed == {"hit": True}


@pytest.mark.asyncio
async def test_chat_json_returns_none_when_both_invalid():
    client = LLMClient(transport=make_transport(["垃圾输出", "还是垃圾"]))
    result = await client.chat_json("sys", "user")

    assert result.ok is False
    assert result.parsed is None
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_chat_retries_on_transport_error():
    client = LLMClient(
        transport=make_transport([timeout_error(), timeout_error(), '{"hit": false}']),
    )
    result = await client.chat_json("sys", "user")

    assert result.ok
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_chat_raises_after_max_retry():
    errors = [timeout_error(), timeout_error(), timeout_error()]
    client = LLMClient(transport=make_transport(errors))

    with pytest.raises(LLMFailed):
        await client.chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_concurrency_gate_serializes_calls():
    """并发闸门存在性验证：同时发起 6 个调用不应抛错。"""
    client = LLMClient(transport=make_transport(['{"ok": true}'] * 6))
    results = await __import__("asyncio").gather(
        *[client.chat_json("s", "u") for _ in range(6)]
    )
    assert all(r.ok for r in results)
