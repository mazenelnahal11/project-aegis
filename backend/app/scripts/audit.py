"""Audit log read + append + report.

`security_audit.log` lives at `<project_dir>/logs/security_audit.log` inside WSL.
We write through WSL so timestamps match what the bash scripts would produce,
keeping the audit trail consistent across CLI and web triggers.
"""
from __future__ import annotations

import re
from datetime import datetime

from ..config import settings
from ..runners import get_runner
from ..wsl_bridge import run_script  # back-compat
from .models import AuditLine


_AUDIT_RE = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+\[(?P<level>[A-Z]+)\]\s+(?P<msg>.*)$")


def _log_path() -> str:
    runner = get_runner()
    if runner.name == "local":
        from pathlib import Path
        # Local: write to <project>/logs/security_audit.log
        project = getattr(runner, "project_dir", Path.cwd())
        return str(Path(project) / "logs" / "security_audit.log")
    # WSL: bash log lives under the WSL-side path
    return f"{settings.project_dir_wsl}/logs/security_audit.log"


def append_audit(level: str, message: str) -> None:
    """Append a single entry. Matches the bash `log()` helper format exactly."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}\n"
    get_runner().write_file_append(_log_path(), line)


def read_audit_lines(*, limit: int = 500, since: str | None = None) -> list[AuditLine]:
    raw = get_runner().read_file(_log_path())
    lines = raw.splitlines()
    parsed: list[AuditLine] = []
    for line in lines:
        m = _AUDIT_RE.match(line)
        if m:
            ts = m.group("ts")
            if since and ts < since:
                continue
            parsed.append(AuditLine(
                timestamp=ts,
                level=m.group("level"),
                message=m.group("msg"),
                raw=line,
            ))
        else:
            parsed.append(AuditLine(timestamp="", level="INFO", message=line, raw=line))
    return parsed[-limit:]


def generate_html_report() -> str:
    """Invoke `4_audit_logger.sh --report` then return the HTML body."""
    today = datetime.now().strftime("%Y-%m-%d")
    run_script("4_audit_logger", ["--report"], timeout=30)
    runner = get_runner()
    if runner.name == "local":
        from pathlib import Path
        project = getattr(runner, "project_dir", Path.cwd())
        report_path = str(Path(project) / "logs" / f"report_{today}.html")
    else:
        report_path = f"{settings.project_dir_wsl}/logs/report_{today}.html"
    return runner.read_file(report_path)


def summary_counts() -> dict[str, int]:
    """Cheap awk-style count for the dashboard cards."""
    counts = {
        "rogue": 0, "sigterm": 0, "sigkill": 0,
        "perm_fixed": 0, "errors": 0, "warns": 0,
    }
    for line in read_audit_lines(limit=10_000):
        msg = line.message
        if "ROGUE PROCESS" in msg:
            counts["rogue"] += 1
        if "SIGTERM sent" in msg:
            counts["sigterm"] += 1
        if "SIGKILL sent" in msg:
            counts["sigkill"] += 1
        if "PERM FIXED" in msg:
            counts["perm_fixed"] += 1
        if line.level == "ERROR":
            counts["errors"] += 1
        if line.level == "WARN":
            counts["warns"] += 1
    return counts
