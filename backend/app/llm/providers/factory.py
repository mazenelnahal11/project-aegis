from __future__ import annotations

from ...config import settings
from .base import LLMProvider

_cached: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _cached
    if _cached is not None:
        return _cached
    name = (settings.llm_provider or "").strip().lower()
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        _cached = AnthropicProvider()
    elif name in {"openai_compat", "openai", "mistral", "groq", "together", "fireworks"}:
        from .openai_compat_provider import OpenAICompatProvider
        _cached = OpenAICompatProvider()
    else:
        raise RuntimeError(f"unknown AEGIS_LLM_PROVIDER: {name!r}")
    return _cached


def reset_provider_cache() -> None:
    """Test hook: drop the cached provider so settings changes take effect."""
    global _cached
    _cached = None
