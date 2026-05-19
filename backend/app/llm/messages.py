"""Canonical, provider-neutral message format.

We persist conversation history in this shape. Each provider implementation
serializes it to its own wire format at call time. This lets us swap providers
mid-session if desired (we don't, but it's cheap).
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str  # JSON-encoded


Block = Union[TextBlock, ToolUseBlock, ToolResultBlock]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: list[Block]


class LLMResponse(BaseModel):
    """Normalized provider response."""

    text_blocks: list[str]
    tool_calls: list[ToolUseBlock]
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "other"]


def text(role: Literal["user", "assistant"], s: str) -> Message:
    return Message(role=role, content=[TextBlock(text=s)])
