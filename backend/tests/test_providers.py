"""Provider abstraction unit tests. Both Anthropic and OpenAI-compat
implementations are exercised with mocked HTTP clients."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.llm.messages import (
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)


# ---------- AnthropicProvider ----------

def _mk_anthropic_response(stop_reason: str, blocks: list):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def test_anthropic_provider_translates_text_and_tool_use(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_api_key", "sk-fake")
    monkeypatch.setattr(settings, "llm_model", "claude-sonnet-4-6")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mk_anthropic_response(
        "tool_use",
        [
            SimpleNamespace(type="text", text="thinking..."),
            SimpleNamespace(type="tool_use", id="tu_1", name="list_processes", input={"only_flagged": True}),
        ],
    )

    with patch("app.llm.providers.anthropic_provider.Anthropic", return_value=fake_client):
        from app.llm.providers.anthropic_provider import AnthropicProvider
        prov = AnthropicProvider()
        out = prov.chat([Message(role="user", content=[TextBlock(text="hi")])])

    assert out.text_blocks == ["thinking..."]
    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "list_processes"
    assert out.tool_calls[0].input == {"only_flagged": True}
    assert out.stop_reason == "tool_use"


# ---------- OpenAICompatProvider ----------

def _mk_openai_response(finish_reason: str, content, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def test_openai_compat_requires_base_url(monkeypatch):
    from app.config import settings
    from app.llm.providers.openai_compat_provider import OpenAICompatProvider
    monkeypatch.setattr(settings, "llm_provider", "openai_compat")
    monkeypatch.setattr(settings, "llm_api_key", "x")
    monkeypatch.setattr(settings, "llm_base_url", "")
    with pytest.raises(RuntimeError, match="AEGIS_LLM_BASE_URL"):
        OpenAICompatProvider()


def test_openai_compat_translates_user_message_to_string(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "x")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.mistral.ai/v1")
    monkeypatch.setattr(settings, "llm_model", "mistral-large-latest")

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _mk_openai_response("stop", "All good.")

    with patch("app.llm.providers.openai_compat_provider.OpenAI", return_value=fake_client):
        from app.llm.providers.openai_compat_provider import OpenAICompatProvider
        prov = OpenAICompatProvider()
        out = prov.chat([Message(role="user", content=[TextBlock(text="who is hogging cpu?")])])

    args = fake_client.chat.completions.create.call_args.kwargs
    msgs = args["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "who is hogging cpu?"}
    assert args["model"] == "mistral-large-latest"
    assert out.text_blocks == ["All good."]
    assert out.tool_calls == []
    assert out.stop_reason == "end_turn"


def test_openai_compat_serializes_tool_use_and_result(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "x")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.mistral.ai/v1")

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _mk_openai_response("stop", "Done.")

    with patch("app.llm.providers.openai_compat_provider.OpenAI", return_value=fake_client):
        from app.llm.providers.openai_compat_provider import OpenAICompatProvider
        prov = OpenAICompatProvider()
        history = [
            Message(role="user", content=[TextBlock(text="check cpu")]),
            Message(role="assistant", content=[
                TextBlock(text="Looking it up."),
                ToolUseBlock(id="call_1", name="list_processes", input={"only_flagged": True}),
            ]),
            Message(role="user", content=[
                ToolResultBlock(tool_use_id="call_1", content=json.dumps({"processes": []})),
            ]),
        ]
        prov.chat(history)

    msgs = fake_client.chat.completions.create.call_args.kwargs["messages"]
    # system, user, assistant(text+tool_calls), tool
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "check cpu"}
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["content"] == "Looking it up."
    assert msgs[2]["tool_calls"][0]["id"] == "call_1"
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "list_processes"
    assert json.loads(msgs[2]["tool_calls"][0]["function"]["arguments"]) == {"only_flagged": True}
    assert msgs[3] == {"role": "tool", "tool_call_id": "call_1", "content": json.dumps({"processes": []})}


def test_openai_compat_translates_tool_call_response(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "x")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.mistral.ai/v1")

    tc = SimpleNamespace(
        id="call_abc",
        function=SimpleNamespace(name="propose_kill_process", arguments=json.dumps({"pid": 1234, "reason": "leak"})),
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _mk_openai_response("tool_calls", None, [tc])

    with patch("app.llm.providers.openai_compat_provider.OpenAI", return_value=fake_client):
        from app.llm.providers.openai_compat_provider import OpenAICompatProvider
        prov = OpenAICompatProvider()
        out = prov.chat([Message(role="user", content=[TextBlock(text="please")])])

    assert out.text_blocks == []
    assert out.stop_reason == "tool_use"
    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "propose_kill_process"
    assert out.tool_calls[0].input == {"pid": 1234, "reason": "leak"}


# ---------- Factory ----------

def test_factory_selects_anthropic(monkeypatch):
    from app.config import settings
    from app.llm.providers import factory
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_api_key", "x")
    factory.reset_provider_cache()
    with patch("app.llm.providers.anthropic_provider.Anthropic"):
        p = factory.get_provider()
    assert p.name == "anthropic"
    factory.reset_provider_cache()


def test_factory_selects_openai_compat_alias(monkeypatch):
    from app.config import settings
    from app.llm.providers import factory
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "llm_api_key", "x")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.mistral.ai/v1")
    factory.reset_provider_cache()
    with patch("app.llm.providers.openai_compat_provider.OpenAI"):
        p = factory.get_provider()
    assert p.name == "openai_compat"
    factory.reset_provider_cache()


def test_factory_rejects_unknown(monkeypatch):
    from app.config import settings
    from app.llm.providers import factory
    monkeypatch.setattr(settings, "llm_provider", "deepmind")
    factory.reset_provider_cache()
    with pytest.raises(RuntimeError, match="unknown"):
        factory.get_provider()
    factory.reset_provider_cache()
