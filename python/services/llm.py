"""Explicit offline default; live providers require a separate opt-in and key."""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

from langchain_openai import ChatOpenAI

from config import get_settings


class OfflineChatModel:
    """Deterministic synthetic model for local demos; no network client."""

    def __init__(self, task: str):
        self.task = task

    async def ainvoke(self, messages):
        text = str(messages[-1].content)
        if self.task == "profile":
            value = {"segments": ["active"], "preferred_categories": [], "price_range": [0, 10000]}
        elif self.task == "rank":
            value = re.findall(r'"id":\s*"([^\"]+)"', text)
        else:
            value = [{"product_id": pid, "copy": "Explore this demo product."}
                     for pid in re.findall(r'ID:([^\s]+)', text)]
        return SimpleNamespace(content=json.dumps(value))


def create_model(task: str, *, temperature: float, max_tokens: int):
    settings = get_settings()
    if settings.llm_mode == "offline":
        return OfflineChatModel(task)
    if not settings.llm_api_key or settings.llm_api_key == "your_api_key_here":
        raise ValueError("Live mode requires a private ECOM_LLM_API_KEY")
    return ChatOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
                      model=settings.llm_model, temperature=temperature,
                      max_tokens=max_tokens, max_retries=0)
