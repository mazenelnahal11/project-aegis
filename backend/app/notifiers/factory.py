from __future__ import annotations

from ..config import settings
from .base import Notifier, NullNotifier

_cached: Notifier | None = None


def get_notifier() -> Notifier:
    global _cached
    if _cached is not None:
        return _cached
    if settings.slack_webhook_url:
        from .slack import SlackNotifier
        _cached = SlackNotifier()
    else:
        _cached = NullNotifier()
    return _cached


def reset_notifier_cache() -> None:
    """Test hook."""
    global _cached
    _cached = None
