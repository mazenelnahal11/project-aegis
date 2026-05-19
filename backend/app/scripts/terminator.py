"""Per-PID termination. Mirrors `2_terminator.sh` semantics for a single PID."""
from __future__ import annotations

import time
from datetime import datetime

from ..config import settings
from ..wsl_bridge import run_inline
from .audit import append_audit


GRACE_SECONDS = 10


def is_alive(pid: int) -> bool:
    res = run_inline(["kill", "-0", str(pid)], timeout=5)
    return res.exit_code == 0


def _proc_info(pid: int) -> tuple[str, str]:
    res = run_inline(["ps", "-p", str(pid), "-o", "user=,comm="], timeout=5)
    parts = res.stdout.strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "?", "?"


def terminate_pid(pid: int, *, grace_seconds: int = GRACE_SECONDS) -> dict:
    """SIGTERM -> wait -> SIGKILL if still alive. Writes audit log entries
    in the SAME format as `2_terminator.sh`.
    """
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    if not is_alive(pid):
        append_audit("INFO", f"PID={pid} already dead before SIGTERM")
        return {
            "pid": pid,
            "outcome": "already_gone",
            "started_at": started,
            "finished_at": started,
            "user": None,
            "command": None,
        }

    user, comm = _proc_info(pid)
    info = f"USER={user}  CMD={comm}"

    term = run_inline(["kill", "-15", str(pid)], timeout=5)
    if not term.ok:
        append_audit("WARN", f"SIGTERM failed | PID={pid} | exit={term.exit_code}")
        return {
            "pid": pid,
            "outcome": "sigterm_failed",
            "started_at": started,
            "finished_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": user,
            "command": comm,
            "stderr": term.stderr,
        }
    append_audit("ACTION", f"SIGTERM sent | PID={pid} | {info} | USER={user}")

    time.sleep(grace_seconds)

    if not is_alive(pid):
        append_audit("ACTION", f"PID={pid} exited cleanly via SIGTERM | USER={user}")
        return {
            "pid": pid,
            "outcome": "sigterm_clean",
            "started_at": started,
            "finished_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": user,
            "command": comm,
        }

    kill = run_inline(["kill", "-9", str(pid)], timeout=5)
    if not kill.ok:
        append_audit("ERROR", f"SIGKILL failed | PID={pid} | exit={kill.exit_code}")
        return {
            "pid": pid,
            "outcome": "sigkill_failed",
            "started_at": started,
            "finished_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": user,
            "command": comm,
            "stderr": kill.stderr,
        }
    append_audit("ACTION", f"SIGKILL sent | PID={pid} | {info} | USER={user}")

    time.sleep(1)
    if is_alive(pid):
        append_audit("ERROR", f"PID={pid} survived SIGKILL - likely D-state")
        outcome = "sigkill_survived"
    else:
        append_audit("ACTION", f"PID={pid} terminated via SIGKILL | USER={user}")
        outcome = "sigkill_clean"

    return {
        "pid": pid,
        "outcome": outcome,
        "started_at": started,
        "finished_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "user": user,
        "command": comm,
    }
