"""LocalRunner — runs commands directly on the host. Use this when Aegis
is deployed on a Linux server (the canonical mode) or inside a Linux
container (the Docker demo).
"""
from __future__ import annotations

import asyncio
import os
import platform
import subprocess
from pathlib import Path
from typing import AsyncIterator

from .base import ScriptResult

ALLOWED_SCRIPTS = {
    "1_process_hunter",
    "2_terminator",
    "3_permission_auditor",
    "4_audit_logger",
}


class LocalRunner:
    name = "local"

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()

    def run_inline(self, argv: list[str], *, timeout: int = 60) -> ScriptResult:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return ScriptResult(stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode)

    def run_script(self, name: str, args: list[str] | None = None, *, timeout: int = 120) -> ScriptResult:
        if name not in ALLOWED_SCRIPTS:
            raise ValueError(f"script '{name}' is not in the allowlist")
        path = self.project_dir / "scripts" / f"{name}.sh"
        return self.run_inline(["bash", str(path), *(args or [])], timeout=timeout)

    def write_file_append(self, path: str, content: str, *, timeout: int = 5) -> None:
        # Ensure parent dir exists, then append atomically-enough for our use.
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

    def read_file(self, path: str, *, timeout: int = 10) -> str:
        p = Path(path)
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8", errors="replace")

    def health_check(self) -> dict:
        return {
            "ok": True,
            "kind": "local",
            "platform": platform.platform(),
            "project_dir": str(self.project_dir),
        }

    async def tail_follow(self, path: str) -> AsyncIterator[str]:
        # Use `tail -n 0 -F` for cross-distro reliability.
        proc = await asyncio.create_subprocess_exec(
            "tail", "-n", "0", "-F", path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            assert proc.stdout is not None
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                yield raw.decode("utf-8", errors="replace").rstrip("\n")
        finally:
            try:
                proc.terminate()
                await proc.wait()
            except ProcessLookupError:
                pass
