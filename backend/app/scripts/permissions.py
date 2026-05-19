"""Permission scan + per-path fix. Mirrors `3_permission_auditor.sh` semantics."""
from __future__ import annotations

import re
from datetime import datetime

from ..wsl_bridge import run_inline
from .audit import append_audit
from .models import PermissionRow, PermissionScanResult

_PATH_RE = re.compile(r"^[A-Za-z0-9_./@\-+:= ]+$")


def _safe_path(path: str) -> str:
    """Reject anything that could shell-glob or escape. Only safe-looking absolute
    paths are accepted. (We pass via argv so this is defense-in-depth.)"""
    if not path.startswith("/") or ".." in path.split("/"):
        raise ValueError(f"unsafe path: {path}")
    if not _PATH_RE.match(path):
        raise ValueError(f"path has disallowed characters: {path}")
    return path


def scan_world_writable(scan_dir: str = "/home") -> PermissionScanResult:
    scan_dir = _safe_path(scan_dir)
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    find_res = run_inline(
        ["find", scan_dir, "-perm", "777", "-printf", "%p|%U|%y\n"],
        timeout=30,
    )

    entries: list[PermissionRow] = []
    for line in find_res.stdout.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        path, owner, ftype = parts
        if ftype == "d":
            recommended = "755"
            type_label = "directory"
        else:
            recommended = "644"
            type_label = "file"
        entries.append(PermissionRow(
            path=path,
            owner=owner,
            file_type=type_label,
            current_mode="777",
            recommended_mode=recommended,
        ))

    return PermissionScanResult(
        scanned_at=started,
        scan_dir=scan_dir,
        entries=entries,
        stderr=find_res.stderr,
    )


def fix_permission(path: str, mode: str) -> dict:
    path = _safe_path(path)
    if mode not in {"755", "644", "750", "640", "700", "600"}:
        raise ValueError(f"disallowed chmod mode: {mode}")

    stat_res = run_inline(["stat", "-c", "%U|%F", path], timeout=5)
    if not stat_res.ok:
        append_audit("ERROR", f"PERM STAT FAILED | PATH={path} | rc={stat_res.exit_code}")
        return {"path": path, "outcome": "stat_failed", "stderr": stat_res.stderr}
    owner, ftype = stat_res.stdout.strip().split("|", 1)

    chmod_res = run_inline(["chmod", mode, path], timeout=5)
    if not chmod_res.ok:
        append_audit("ERROR", f"PERM FIX FAILED | PATH={path} | OWNER={owner} | rc={chmod_res.exit_code}")
        return {
            "path": path,
            "outcome": "chmod_failed",
            "owner": owner,
            "stderr": chmod_res.stderr,
        }

    append_audit(
        "ACTION",
        f"PERM FIXED | PATH={path} | TYPE={ftype} | OWNER={owner} | 777 -> {mode}",
    )
    return {
        "path": path,
        "outcome": "fixed",
        "owner": owner,
        "type": ftype,
        "new_mode": mode,
    }
