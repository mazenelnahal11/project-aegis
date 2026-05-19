"""Dispatch Claude tool calls. Read-only tools run immediately; destructive
tools become pending gates and return `requires_confirmation: true`.
"""
from __future__ import annotations

from typing import Any

from ..gates import create_gate
from ..scripts.audit import read_audit_lines, summary_counts
from ..scripts.permissions import scan_world_writable
from ..scripts.process_hunter import list_processes


def execute_tool(
    name: str,
    args: dict[str, Any],
    *,
    chat_session_id: str | None,
    tool_use_id: str,
) -> dict:
    if name == "list_processes":
        rows = list_processes(only_flagged=bool(args.get("only_flagged", False)))
        limit = int(args.get("limit", 50))
        return {"processes": [r.model_dump(by_alias=True) for r in rows[:limit]]}

    if name == "list_world_writable":
        res = scan_world_writable(args.get("dir", "/home"))
        return res.model_dump(by_alias=True)

    if name == "get_audit_log":
        lines = read_audit_lines(
            limit=int(args.get("limit", 100)),
            since=args.get("since"),
        )
        return {"lines": [line.model_dump() for line in lines]}

    if name == "get_audit_summary":
        return summary_counts()

    if name == "propose_kill_process":
        pid = int(args["pid"])
        gate = create_gate(
            kind="kill",
            payload={"pid": pid, "reason": args.get("reason", "")},
            origin="llm",
            chat_session_id=chat_session_id,
            tool_use_id=tool_use_id,
        )
        return {
            "gate_id": gate["id"],
            "kind": "kill",
            "preview": f"kill -15 {pid}; sleep 10; kill -9 {pid} (if alive)",
            "requires_confirmation": True,
            "executed": False,
        }

    if name == "propose_fix_permission":
        path = args["path"]
        mode = args["mode"]
        gate = create_gate(
            kind="fix_permission",
            payload={"path": path, "mode": mode, "reason": args.get("reason", "")},
            origin="llm",
            chat_session_id=chat_session_id,
            tool_use_id=tool_use_id,
        )
        return {
            "gate_id": gate["id"],
            "kind": "fix_permission",
            "preview": f"chmod {mode} {path}",
            "requires_confirmation": True,
            "executed": False,
        }

    return {"error": f"unknown tool: {name}"}
