from __future__ import annotations

from typing import cast

from anthropic import Anthropic

from ...config import settings
from ..messages import LLMResponse, Message, ToolUseBlock
from ..system_prompt import SYSTEM_PROMPT
from ..tools import TOOLS


def _system_block() -> list[dict]:
    return [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]


def _tools_block() -> list[dict]:
    out: list[dict] = []
    for i, tool in enumerate(TOOLS):
        entry = dict(tool)
        if i == len(TOOLS) - 1:
            entry["cache_control"] = {"type": "ephemeral"}
        out.append(entry)
    return out


def _msg_to_anthropic(m: Message) -> dict:
    """Map canonical → Anthropic wire format.

    Anthropic's API expects tool_result blocks on a `user` role message.
    Our canonical format keeps tool_use on assistant and tool_result on user,
    which already matches — so this is mostly a 1:1 dict copy.
    """
    return {"role": m.role, "content": [b.model_dump() for b in m.content]}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self.model = settings.llm_model
        self._client = Anthropic(api_key=settings.effective_llm_api_key)

    def chat(self, messages: list[Message]) -> LLMResponse:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_system_block(),
            tools=_tools_block(),
            messages=[_msg_to_anthropic(m) for m in messages],
        )

        text_blocks: list[str] = []
        tool_calls: list[ToolUseBlock] = []
        for block in resp.content:
            if block.type == "text":
                text_blocks.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolUseBlock(id=block.id, name=block.name, input=dict(block.input))
                )

        stop = "tool_use" if resp.stop_reason == "tool_use" else (
            "end_turn" if resp.stop_reason in ("end_turn", "stop_sequence") else
            "max_tokens" if resp.stop_reason == "max_tokens" else "other"
        )
        return LLMResponse(text_blocks=text_blocks, tool_calls=tool_calls, stop_reason=cast(str, stop))
