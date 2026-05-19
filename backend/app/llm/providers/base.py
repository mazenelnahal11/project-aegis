from __future__ import annotations

from typing import Protocol

from ..messages import LLMResponse, Message


class LLMProvider(Protocol):
    """Provider-agnostic chat interface.

    `chat(messages)` returns a normalized LLMResponse. Implementations are
    responsible for converting our canonical Message format into their wire
    format and back.
    """

    name: str
    model: str

    def chat(self, messages: list[Message]) -> LLMResponse: ...
