"""OpenAI-compatible provider.

Works with any endpoint that speaks the OpenAI chat-completions wire format
with tool calls: OpenAI, Mistral, Groq, Together, Fireworks, DeepInfra, etc.

Configure via:
  AEGIS_LLM_PROVIDER=openai_compat
  AEGIS_LLM_BASE_URL=https://api.mistral.ai/v1
  AEGIS_LLM_MODEL=mistral-large-latest
  AEGIS_LLM_API_KEY=<key>
"""
from __future__ import annotations

import json
from typing import cast

from openai import OpenAI

from ...config import settings
from ..messages import LLMResponse, Message, ToolResultBlock, ToolUseBlock
from ..system_prompt import SYSTEM_PROMPT
from ..tools import TOOLS


def _tools_for_openai() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


def _canonical_to_openai(messages: list[Message]) -> list[dict]:
    """Translate our canonical messages to OpenAI chat-completions format.

    - canonical `user`/[TextBlock]                → {"role": "user", "content": str}
    - canonical `assistant`/[Text + ToolUse...]   → {"role": "assistant",
                                                     "content": text or None,
                                                     "tool_calls": [...]}
    - canonical `user`/[ToolResult...]            → one `{"role": "tool", ...}` per result
    """
    out: list[dict] = []
    for m in messages:
        if m.role == "user":
            tool_results = [b for b in m.content if isinstance(b, ToolResultBlock)]
            if tool_results:
                for tr in tool_results:
                    out.append({"role": "tool", "tool_call_id": tr.tool_use_id, "content": tr.content})
                # Any text alongside tool results becomes a separate user message
                texts = [b for b in m.content if b.type == "text"]
                for t in texts:
                    out.append({"role": "user", "content": t.text})  # type: ignore[attr-defined]
            else:
                text = "".join(b.text for b in m.content if b.type == "text")  # type: ignore[attr-defined]
                out.append({"role": "user", "content": text})
        else:  # assistant
            text_parts = [b.text for b in m.content if b.type == "text"]  # type: ignore[attr-defined]
            tool_uses = [b for b in m.content if isinstance(b, ToolUseBlock)]
            msg: dict = {"role": "assistant"}
            msg["content"] = "".join(text_parts) or None
            if tool_uses:
                msg["tool_calls"] = [
                    {
                        "id": tu.id,
                        "type": "function",
                        "function": {"name": tu.name, "arguments": json.dumps(tu.input)},
                    }
                    for tu in tool_uses
                ]
            out.append(msg)
    return out


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self) -> None:
        self.model = settings.llm_model
        if not settings.llm_base_url:
            raise RuntimeError(
                "OpenAI-compatible providers require AEGIS_LLM_BASE_URL "
                "(e.g. https://api.mistral.ai/v1)"
            )
        self._client = OpenAI(
            api_key=settings.effective_llm_api_key,
            base_url=settings.llm_base_url,
        )

    def chat(self, messages: list[Message]) -> LLMResponse:
        wire_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _canonical_to_openai(messages)

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=wire_messages,
            tools=_tools_for_openai(),
            tool_choice="auto",
            max_tokens=2048,
        )

        choice = resp.choices[0]
        msg = choice.message
        text_blocks: list[str] = []
        if msg.content:
            text_blocks.append(msg.content)

        tool_calls: list[ToolUseBlock] = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolUseBlock(id=tc.id, name=tc.function.name, input=args))

        finish = choice.finish_reason
        if finish == "tool_calls":
            stop = "tool_use"
        elif finish == "stop":
            stop = "end_turn"
        elif finish == "length":
            stop = "max_tokens"
        else:
            stop = "other"

        return LLMResponse(text_blocks=text_blocks, tool_calls=tool_calls, stop_reason=cast(str, stop))
