from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    """One-way notification channel.

    Implementations send an outbound message and return. Acknowledgements come
    back through the Aegis web endpoint via a single-use token, not through the
    channel itself — so this Protocol stays a pure sender.
    """

    name: str

    def send_grace_warning(
        self,
        *,
        owner_id: str,
        owner_label: str,
        action_summary: str,
        reason: str,
        deadline_iso: str,
        ack_url: str,
    ) -> None: ...


class NullNotifier:
    """Used when no channel is configured. Records the would-be message so
    tests can assert, and keeps the API working in unconfigured environments.
    """

    name = "null"

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_grace_warning(
        self,
        *,
        owner_id: str,
        owner_label: str,
        action_summary: str,
        reason: str,
        deadline_iso: str,
        ack_url: str,
    ) -> None:
        self.sent.append({
            "owner_id": owner_id,
            "owner_label": owner_label,
            "action_summary": action_summary,
            "reason": reason,
            "deadline_iso": deadline_iso,
            "ack_url": ack_url,
        })
