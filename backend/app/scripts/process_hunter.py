"""Wraps `1_process_hunter.sh` and parses its log output.

Strategy: run a *current* `ps` snapshot via WSL (for the full process list),
then run the bash script to capture flagged PIDs from `/tmp/aegis_pids.txt`
and reasons from the most recent `ROGUE PROCESS` entries in the audit log.

The bash script remains the canonical detector — Python only enriches the view.
"""
from __future__ import annotations

import re
from datetime import datetime

from ..config import settings
from ..wsl_bridge import read_file, run_inline, run_script
from .models import ProcessRow, ScanResult

_PS_FMT = "pid,user:32,%cpu,%mem,etimes,stat,comm"

CPU_LIMIT = 80
TIME_LIMIT_S = 86_400  # 24h, matches 1_process_hunter.sh

SYSTEM_USERS = {
    "root", "daemon", "nobody", "www-data", "systemd+", "dbus",
    "syslog", "messagebus",
}

_ROGUE_LINE_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+\[WARN\]\s+ROGUE PROCESS\s+\|\s+"
    r"PID=(?P<pid>\d+)\s+\|\s+USER=(?P<user>\S+)\s+\|\s+CMD=(?P<cmd>\S+)\s+\|\s+"
    r"(?P<reason>.+?)\s+\|\s+MEM=(?P<mem>[\d.]+)%\s*$"
)


def _parse_ps(raw: str) -> list[ProcessRow]:
    rows: list[ProcessRow] = []
    for line in raw.splitlines():
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        pid, user, cpu, mem, etimes, stat, comm = parts
        try:
            rows.append(ProcessRow(
                pid=int(pid),
                user=user,
                cpu_pct=float(cpu),
                mem_pct=float(mem),
                runtime_seconds=int(etimes),
                state=stat,
                command=comm,
            ))
        except ValueError:
            continue
    return rows


def _apply_flagging(rows: list[ProcessRow]) -> None:
    for r in rows:
        if r.user in SYSTEM_USERS:
            continue
        reasons: list[str] = []
        if r.runtime_seconds >= TIME_LIMIT_S:
            reasons.append(f"Runtime={r.runtime_seconds // 3600}h (>= 24h)")
        if int(r.cpu_pct) >= CPU_LIMIT:
            reasons.append(f"CPU={r.cpu_pct}% (>= {CPU_LIMIT}%)")
        if r.state and r.state[0] in {"Z", "T", "D"}:
            reasons.append(f"State={r.state}")
        if reasons:
            r.flagged = True
            r.reasons = reasons


def list_processes(*, only_flagged: bool = False) -> list[ProcessRow]:
    """Read-only listing. Does NOT invoke the bash script. Safe for the LLM."""
    result = run_inline(["ps", "-eo", _PS_FMT, "--no-headers"], timeout=15)
    rows = _parse_ps(result.stdout)
    _apply_flagging(rows)
    if only_flagged:
        rows = [r for r in rows if r.flagged]
    return rows


def run_hunter_scan() -> ScanResult:
    """Invoke the canonical bash detector + return its findings.

    Side effects: writes to `logs/security_audit.log` and `/tmp/aegis_pids.txt`
    inside WSL (this is the expected/desired behavior — keeps the audit trail
    consistent with CLI runs of `aegis_master.sh`).
    """
    started = datetime.utcnow()
    script_res = run_script("1_process_hunter", timeout=60)
    pid_file = read_file("/tmp/aegis_pids.txt")
    flagged_pids = [int(p) for p in pid_file.split() if p.isdigit()]

    rows = list_processes()
    flagged_set = set(flagged_pids)
    for r in rows:
        if r.pid in flagged_set and not r.flagged:
            r.flagged = True
            r.reasons = r.reasons or ["flagged by hunter script"]

    return ScanResult(
        scanned_at=started.isoformat(timespec="seconds") + "Z",
        processes=rows,
        flagged_pids=flagged_pids,
        stderr=script_res.stderr,
    )


def parse_rogue_log_lines(log_text: str) -> list[dict]:
    """Useful for tests + the audit log page."""
    out: list[dict] = []
    for line in log_text.splitlines():
        m = _ROGUE_LINE_RE.match(line)
        if m:
            out.append(m.groupdict())
    return out


__all__ = [
    "list_processes",
    "run_hunter_scan",
    "parse_rogue_log_lines",
    "CPU_LIMIT",
    "TIME_LIMIT_S",
]
