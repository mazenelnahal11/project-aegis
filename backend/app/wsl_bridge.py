"""Thin layer that runs commands inside a WSL distro.

Two surfaces:

1. `run_script(name, args)` — invoke one of the bash scripts shipped with the project.
2. `run_inline(argv)` — run an arbitrary command inside WSL via argv (no shell, no injection).

Both ultimately call `wsl.exe -d <distro> -- <argv...>`. We never use `shell=True`,
and inputs are validated by the callers.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .config import settings

ALLOWED_SCRIPTS = {
    "1_process_hunter",
    "2_terminator",
    "3_permission_auditor",
    "4_audit_logger",
}


@dataclass
class ScriptResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class WSLUnavailableError(RuntimeError):
    pass


def _wsl_executable() -> str:
    exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if not exe:
        raise WSLUnavailableError("wsl.exe not found on PATH")
    return exe


def health_check() -> dict:
    """Return a small status report about WSL availability and the configured distro."""
    try:
        exe = _wsl_executable()
    except WSLUnavailableError as e:
        return {"ok": False, "reason": str(e)}
    proc = subprocess.run(
        [exe, "-l", "-q"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    distros = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if settings.wsl_distro not in distros:
        return {
            "ok": False,
            "reason": f"distro '{settings.wsl_distro}' not installed",
            "available": distros,
        }
    probe = run_inline(["bash", "-lc", "echo ok && uname -s"], timeout=10)
    if not probe.ok:
        return {"ok": False, "reason": f"probe failed: {probe.stderr.strip()}"}
    return {"ok": True, "distro": settings.wsl_distro, "kernel": probe.stdout.strip()}


def run_inline(argv: list[str], *, timeout: int = 60) -> ScriptResult:
    exe = _wsl_executable()
    proc = subprocess.run(
        [exe, "-d", settings.wsl_distro, "--", *argv],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return ScriptResult(stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode)


def run_script(name: str, args: list[str] | None = None, *, timeout: int = 120) -> ScriptResult:
    if name not in ALLOWED_SCRIPTS:
        raise ValueError(f"script '{name}' is not in the allowlist")
    args = args or []
    script_path = f"{settings.project_dir_wsl}/scripts/{name}.sh"
    return run_inline(["bash", script_path, *args], timeout=timeout)


def read_file(wsl_path: str, *, timeout: int = 10) -> str:
    return run_inline(["cat", wsl_path], timeout=timeout).stdout
