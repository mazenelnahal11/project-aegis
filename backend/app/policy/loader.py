"""User policy loader. Reads the YAML at startup; can be reloaded at runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import settings


@dataclass
class UserPolicy:
    by_user: dict[str, dict] = field(default_factory=dict)
    default_slack_id: str = ""

    def slack_id_for(self, linux_user: str) -> str:
        entry = self.by_user.get(linux_user) or {}
        sid = entry.get("slack_id") or self.default_slack_id
        return sid


_cached: UserPolicy | None = None


def load_policy(path: Path | None = None) -> UserPolicy:
    p = path or settings.users_yaml_path
    if not p.exists():
        return UserPolicy()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    users = raw.get("users") or {}
    default = (users.get("default") or {}).get("slack_id", "")
    by_user = {k: v for k, v in users.items() if k != "default" and isinstance(v, dict)}
    return UserPolicy(by_user=by_user, default_slack_id=default)


def policy() -> UserPolicy:
    global _cached
    if _cached is None:
        _cached = load_policy()
    return _cached


def reload_policy() -> UserPolicy:
    global _cached
    _cached = load_policy()
    return _cached
