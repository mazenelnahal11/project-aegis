"""Thin Anthropic SDK wrapper with prompt caching on the system prompt + tools."""
from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from ..config import settings
from .system_prompt import SYSTEM_PROMPT
from .tools import TOOLS

_client: Anthropic | None = None


def client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def system_block() -> list[dict]:
    return [{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]


def tools_block() -> list[dict]:
    cached: list[dict] = []
    for i, tool in enumerate(TOOLS):
        entry = dict(tool)
        if i == len(TOOLS) - 1:
            entry["cache_control"] = {"type": "ephemeral"}
        cached.append(entry)
    return cached


def call_model(messages: list[dict]) -> Any:  # type: ignore[valid-type]
    return client().messages.create(
        model=settings.llm_model,
        max_tokens=2048,
        system=system_block(),
        tools=tools_block(),
        messages=messages,
    )
