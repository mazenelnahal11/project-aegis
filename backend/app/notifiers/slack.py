"""Slack notifier — incoming-webhook only, no OAuth, no public receiver.

Outbound only: posts a Block Kit message to the configured webhook with a
single-use ack URL. Acknowledgement comes back through `/api/grace/ack/<token>`
on the Aegis web app, not through Slack.
"""
from __future__ import annotations

import httpx

from ..config import settings


class SlackNotifier:
    name = "slack"

    def __init__(self, webhook_url: str | None = None, *, timeout: float = 5.0) -> None:
        self.webhook_url = webhook_url or settings.slack_webhook_url
        self.timeout = timeout
        if not self.webhook_url:
            raise RuntimeError("SlackNotifier requires AEGIS_SLACK_WEBHOOK_URL")

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
        # Slack incoming webhooks are channel-scoped, not DM-scoped. We mention
        # the user by Slack ID inside the message; the webhook fans out to the
        # configured channel (typically a small ops/server-admins channel).
        text_fallback = (
            f"<@{owner_id}> Aegis flagged your process — "
            f"{action_summary}. Reason: {reason}. "
            f"Deadline: {deadline_iso}. Acknowledge: {ack_url}"
        )
        payload = {
            "text": text_fallback,  # required by Slack as fallback
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🛡  Aegis — process flagged"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"<@{owner_id}> *{action_summary}*\n"
                            f"_Reason:_ {reason}\n"
                            f"_Deadline:_ `{deadline_iso}`"
                        ),
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Acknowledge / extend"},
                            "url": ack_url,
                            "style": "primary",
                        }
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Linux user: `{owner_label}`"},
                    ],
                },
            ],
        }
        # Fire and (mostly) forget. Caller logs failures.
        resp = httpx.post(self.webhook_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
