"""统一 LLM 调用入口（文档 3.3 / 11 节）。

约定：
- 业务代码只通过本模块调用模型，禁止在别处 new 客户端或硬编码模型名
- 供应商切换只改 .env（LLM_BASE_URL / LLM_MODEL）
- 全局并发闸门，避免把供应商限流打爆
- JSON 解析失败重试一次，仍失败返回 parsed=None，由上层按"置信度 0、需人工复核"处理
- **日志只记录长度与哈希，绝不打印合同或法条正文**
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.errors import LLMFailed
from app.core.logging import get_logger

log = get_logger(__name__)

# transport 便于测试注入：async (messages, json_mode, max_tokens) -> (content, usage, model)
Transport = Callable[[list[dict[str, str]], bool, int], Awaitable[tuple[str, dict[str, int], str]]]

_FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)
_semaphore: asyncio.Semaphore | None = None
_semaphore_lock = asyncio.Lock()


@dataclass
class LLMResult:
    content: str
    parsed: dict[str, Any] | None
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    attempts: int

    @property
    def ok(self) -> bool:
        return self.parsed is not None

    @property
    def cost_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def extract_json(text: str) -> dict[str, Any] | None:
    """从模型输出里取出 JSON 对象。

    容忍三种脏输出：markdown 代码块包裹、前后有解释性文字、多行 JSON。
    """
    if not text:
        return None

    cleaned = _FENCE.sub("", text).replace("```", "").strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(cleaned[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def text_digest(text: str) -> str:
    """只留摘要用于排障，不落原文。"""
    return f"len={len(text)} sha1={hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"


async def _get_semaphore(limit: int) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        async with _semaphore_lock:
            if _semaphore is None:
                _semaphore = asyncio.Semaphore(max(1, limit))
    return _semaphore


class LLMClient:
    def __init__(
        self, settings: Settings | None = None, transport: Transport | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self._transport = transport
        self._client: AsyncOpenAI | None = None

    # ---- 底层 ----
    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.settings.llm_configured:
                raise LLMFailed("未配置 LLM（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 不完整）")
            self._client = AsyncOpenAI(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                timeout=self.settings.llm_timeout,
                max_retries=0,  # 重试由本模块控制，便于统一计数与日志
            )
        return self._client

    async def _call_api(
        self, messages: list[dict[str, str]], json_mode: bool, max_tokens: int
    ) -> tuple[str, dict[str, int], str]:
        if self._transport is not None:
            return await self._transport(messages, json_mode, max_tokens)

        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = await client.chat.completions.create(**kwargs)
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
        }
        content = resp.choices[0].message.content or ""
        return content, usage, getattr(resp, "model", self.settings.llm_model)

    # ---- 对外 ----
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = True,
        max_tokens: int = 1200,
    ) -> LLMResult:
        """带并发闸门、超时与重试的单次调用。失败抛 LLMFailed。"""
        sem = await _get_semaphore(self.settings.llm_max_concurrency)
        attempts = 0
        last_error: Exception | None = None
        started = time.perf_counter()

        async with sem:
            while attempts <= self.settings.llm_max_retry:
                attempts += 1
                try:
                    content, usage, model = await self._call_api(messages, json_mode, max_tokens)
                    elapsed = int((time.perf_counter() - started) * 1000)
                    return LLMResult(
                        content=content,
                        parsed=extract_json(content) if json_mode else None,
                        model=model,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        latency_ms=elapsed,
                        attempts=attempts,
                    )
                except (APITimeoutError, APIConnectionError, APIError) as exc:
                    last_error = exc
                    log.warning(
                        "llm call failed attempt=%s/%s err=%s",
                        attempts,
                        self.settings.llm_max_retry + 1,
                        type(exc).__name__,
                    )
                    if attempts > self.settings.llm_max_retry:
                        break
                    await asyncio.sleep(0.8 * attempts)

        raise LLMFailed(f"模型调用失败：{type(last_error).__name__ if last_error else 'unknown'}")

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1200,
        retry_on_invalid: bool = True,
    ) -> LLMResult:
        """要求模型输出 JSON；解析失败时补一句纠正再试一次（文档 11 节）。"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        result = await self.chat(messages, json_mode=True, max_tokens=max_tokens)
        if result.ok or not retry_on_invalid:
            return result

        log.warning("json parse failed, retry once: %s", text_digest(result.content))
        messages.append({"role": "assistant", "content": result.content[:500]})
        messages.append(
            {
                "role": "user",
                "content": (
                    "上面的输出不是合法 JSON。请只输出一个 JSON 对象，"
                    "不要 markdown 代码块，不要任何解释文字。"
                ),
            }
        )
        retried = await self.chat(messages, json_mode=True, max_tokens=max_tokens)
        return LLMResult(
            content=retried.content,
            parsed=retried.parsed,
            model=retried.model,
            prompt_tokens=result.prompt_tokens + retried.prompt_tokens,
            completion_tokens=result.completion_tokens + retried.completion_tokens,
            latency_ms=result.latency_ms + retried.latency_ms,
            attempts=result.attempts + retried.attempts,
        )

    async def ping(self, max_tokens: int = 16) -> str:
        """连通性自检：只发一句最小请求，不消耗额度。"""
        result = await self.chat(
            [{"role": "user", "content": "回复两个字：可用"}],
            json_mode=False,
            max_tokens=max_tokens,
        )
        return result.content.strip()


def get_client() -> LLMClient:
    return LLMClient()
