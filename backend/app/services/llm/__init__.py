"""LLM 统一调用入口。"""

from app.services.llm.client import LLMClient, LLMResult, extract_json, get_client

__all__ = ["LLMClient", "LLMResult", "extract_json", "get_client"]
