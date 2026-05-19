"""Grace-period state machine.

Lifecycle:

  pending action  ─create_warning─▶  sent ──(user clicks STOP)──▶ stop
                                       │
                                       ├──(user clicks EXPLAIN)──▶ explained
                                       │
                                       └──(deadline elapsed)─────▶ expired
                                                                      │
                                                                      └─escalate─▶ escalated
                                                                         (creates a
                                                                          pending_actions
                                                                          gate)
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from .config import settings
from .db import conn, dumps, loads, now_iso, tx
from .gates import create_gate
from .notifiers import get_notifier
from .policy.loader import policy
from .scripts.audit import append_audit

Kind = Literal["kill", "fix_permission"]
Status = Literal["sent", "stop", "explained", "expired", "escalated", "failed"]


class Warning(TypedDict):
    id: int
    target_kind: Kind
    target_payload: dict
    owner_linux_user: str | None
    owner_slack_id: str | None
    channel: str
    reason: str
    ack_token: str
    sent_at: str
    expires_at: str
    status: Status
    ack_at: str | None
    ack_action: str | None
    ack_reason: str | None
    escalated_gate_id: int | None
    origin: str


def _row_to_warning(row) -> Warning:
    return Warning(
        id=row["id"],
        target_kind=row["target_kind"],
        target_payload=loads(row["target_payload"]) or {},
        owner_linux_user=row["owner_linux_user"],
        owner_slack_id=row["owner_slack_id"],
        channel=row["channel"],
        reason=row["reason"],
        ack_token=row["ack_token"],
        sent_at=row["sent_at"],
        expires_at=row["expires_at"],
        status=row["status"],
        ack_at=row["ack_at"],
        ack_action=row["ack_action"],
        ack_reason=row["ack_reason"],
        escalated_gate_id=row["escalated_gate_id"],
        origin=row["origin"],
    )


def _action_summary(kind: Kind, payload: dict) -> str:
    if kind == "kill":
        return f"PID {payload.get('pid')} will be terminated"
    if kind == "fix_permission":
        return f"chmod {payload.get('mode')} {payload.get('path')}"
    return f"{kind} {payload}"


def create_warning(
    *,
    target_kind: Kind,
    target_payload: dict,
    owner_linux_user: str,
    reason: str,
    grace_minutes: int | None = None,
    origin: str = "ui",
) -> Warning:
    """Create a warning row and dispatch the notification.

    Note: notifier failures don't roll back the warning — the row stays in
    `sent` state and the dashboard surfaces the channel error. This avoids
    silent drops if Slack is temporarily flaky.
    """
    minutes = grace_minutes or settings.grace_default_minutes
    sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = sent_at + timedelta(minutes=minutes)
    token = secrets.token_urlsafe(24)
    slack_id = policy().slack_id_for(owner_linux_user)

    notifier = get_notifier()
    channel = notifier.name

    with tx() as c:
        cur = c.execute(
            """INSERT INTO grace_warnings
               (target_kind, target_payload, owner_linux_user, owner_slack_id,
                channel, reason, ack_token, sent_at, expires_at, status, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent', ?)""",
            (
                target_kind,
                dumps(target_payload),
                owner_linux_user,
                slack_id,
                channel,
                reason,
                token,
                sent_at.isoformat(timespec="seconds") + "Z",
                expires_at.isoformat(timespec="seconds") + "Z",
                origin,
            ),
        )
        warn_id = cur.lastrowid

    ack_url = f"{settings.ack_base_url.rstrip('/')}/api/grace/ack/{token}"
    summary = _action_summary(target_kind, target_payload)
    try:
        notifier.send_grace_warning(
            owner_id=slack_id,
            owner_label=owner_linux_user,
            action_summary=summary,
            reason=reason,
            deadline_iso=expires_at.isoformat(timespec="seconds") + "Z",
            ack_url=ack_url,
        )
        append_audit(
            "ACTION",
            f"GRACE WARNING SENT | id={warn_id} | user={owner_linux_user} | "
            f"channel={channel} | deadline={expires_at.isoformat(timespec='seconds')}Z | "
            f"target={summary}",
        )
    except Exception as e:
        with tx() as c:
            c.execute("UPDATE grace_warnings SET status='failed' WHERE id=?", (warn_id,))
        append_audit("ERROR", f"GRACE NOTIFY FAILED | id={warn_id} | err={e}")

    return get_warning(warn_id)


def get_warning(warn_id: int) -> Warning:
    row = conn().execute("SELECT * FROM grace_warnings WHERE id=?", (warn_id,)).fetchone()
    if not row:
        raise KeyError(f"warning {warn_id} not found")
    return _row_to_warning(row)


def get_by_token(token: str) -> Warning:
    row = conn().execute("SELECT * FROM grace_warnings WHERE ack_token=?", (token,)).fetchone()
    if not row:
        raise KeyError("token not found")
    return _row_to_warning(row)


def list_warnings(*, status: Status | None = None, limit: int = 100) -> list[Warning]:
    sql = "SELECT * FROM grace_warnings"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY id DESC LIMIT ?"
    args = args + (limit,)
    return [_row_to_warning(r) for r in conn().execute(sql, args).fetchall()]


def acknowledge(token: str, *, action: Literal["stop", "explain"], reason: str | None = None) -> Warning:
    w = get_by_token(token)
    if w["status"] != "sent":
        return w  # idempotent — second click sees the prior decision
    if datetime.fromisoformat(w["expires_at"].rstrip("Z")) < datetime.now(timezone.utc).replace(tzinfo=None):
        # Expired between send and click — let the sweeper handle escalation.
        return w
    new_status: Status = "stop" if action == "stop" else "explained"
    with tx() as c:
        c.execute(
            """UPDATE grace_warnings
               SET status=?, ack_action=?, ack_reason=?, ack_at=?
               WHERE id=? AND status='sent'""",
            (new_status, action, reason, now_iso(), w["id"]),
        )
    append_audit(
        "ACTION",
        f"GRACE ACK | id={w['id']} | user={w['owner_linux_user']} | "
        f"action={action} | reason={reason or '(none)'}",
    )
    return get_warning(w["id"])


def expire_overdue() -> list[Warning]:
    """Find `sent` warnings past their deadline, escalate each to a gate."""
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
    rows = conn().execute(
        "SELECT * FROM grace_warnings WHERE status='sent' AND expires_at <= ?",
        (now,),
    ).fetchall()

    escalated: list[Warning] = []
    for row in rows:
        w = _row_to_warning(row)
        try:
            gate = create_gate(
                kind=w["target_kind"],  # type: ignore[arg-type]
                payload={**w["target_payload"], "grace_warning_id": w["id"], "reason": w["reason"]},
                origin="grace_expiry",
            )
            with tx() as c:
                c.execute(
                    "UPDATE grace_warnings SET status='escalated', escalated_gate_id=? WHERE id=?",
                    (gate["id"], w["id"]),
                )
            append_audit(
                "WARN",
                f"GRACE EXPIRED -> GATE | warning_id={w['id']} | gate_id={gate['id']} | "
                f"user={w['owner_linux_user']}",
            )
            escalated.append(get_warning(w["id"]))
        except Exception as e:
            with tx() as c:
                c.execute("UPDATE grace_warnings SET status='expired' WHERE id=?", (w["id"],))
            append_audit("ERROR", f"GRACE ESCALATION FAILED | id={w['id']} | err={e}")
    return escalated
