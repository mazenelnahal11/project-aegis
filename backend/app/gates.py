"""Pending-action gate table: every destructive action lands here first
and only runs after a human (or the same human via the LLM flow) approves.
"""
from __future__ import annotations

from typing import Literal, TypedDict

from .db import conn, dumps, loads, now_iso, tx
from .scripts.permissions import fix_permission
from .scripts.terminator import terminate_pid

Kind = Literal["kill", "fix_permission"]
Status = Literal["pending", "approved", "rejected", "executed", "failed"]


class Gate(TypedDict):
    id: int
    kind: Kind
    payload: dict
    origin: str
    status: Status
    requested_at: str
    executed_at: str | None
    result: dict | None
    chat_session_id: str | None
    tool_use_id: str | None


def _row_to_gate(row) -> Gate:
    return Gate(
        id=row["id"],
        kind=row["kind"],
        payload=loads(row["payload_json"]) or {},
        origin=row["origin"],
        status=row["status"],
        requested_at=row["requested_at"],
        executed_at=row["executed_at"],
        result=loads(row["result_json"]),
        chat_session_id=row["chat_session_id"],
        tool_use_id=row["tool_use_id"],
    )


def create_gate(
    *,
    kind: Kind,
    payload: dict,
    origin: str,
    chat_session_id: str | None = None,
    tool_use_id: str | None = None,
) -> Gate:
    with tx() as c:
        cur = c.execute(
            """INSERT INTO pending_actions
               (kind, payload_json, origin, status, requested_at, chat_session_id, tool_use_id)
               VALUES (?, ?, ?, 'pending', ?, ?, ?)""",
            (kind, dumps(payload), origin, now_iso(), chat_session_id, tool_use_id),
        )
        gate_id = cur.lastrowid
    return get_gate(gate_id)


def get_gate(gate_id: int) -> Gate:
    row = conn().execute(
        "SELECT * FROM pending_actions WHERE id = ?", (gate_id,)
    ).fetchone()
    if not row:
        raise KeyError(f"gate {gate_id} not found")
    return _row_to_gate(row)


def list_gates(*, status: Status | None = None, limit: int = 100) -> list[Gate]:
    sql = "SELECT * FROM pending_actions"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY id DESC LIMIT ?"
    args = args + (limit,)
    return [_row_to_gate(r) for r in conn().execute(sql, args).fetchall()]


def reject_gate(gate_id: int) -> Gate:
    with tx() as c:
        c.execute(
            "UPDATE pending_actions SET status='rejected', executed_at=? WHERE id=? AND status='pending'",
            (now_iso(), gate_id),
        )
    return get_gate(gate_id)


def approve_and_execute(gate_id: int) -> Gate:
    """Approve the gate and run the underlying script primitive.

    Each `kind` maps to exactly one safe primitive in `scripts/`.
    """
    gate = get_gate(gate_id)
    if gate["status"] != "pending":
        return gate

    payload = gate["payload"]
    result: dict
    status: Status

    try:
        if gate["kind"] == "kill":
            pid = int(payload["pid"])
            result = terminate_pid(pid)
            status = "executed"
        elif gate["kind"] == "fix_permission":
            result = fix_permission(payload["path"], payload["mode"])
            status = "executed" if result.get("outcome") == "fixed" else "failed"
        else:
            raise ValueError(f"unknown kind: {gate['kind']}")
    except Exception as e:
        result = {"error": str(e)}
        status = "failed"

    with tx() as c:
        c.execute(
            "UPDATE pending_actions SET status=?, executed_at=?, result_json=? WHERE id=?",
            (status, now_iso(), dumps(result), gate_id),
        )
    return get_gate(gate_id)
