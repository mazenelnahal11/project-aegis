"""Back-compat shim. New code should `from .runners import get_runner`.

This module is preserved so existing imports (`from .wsl_bridge import run_inline`)
keep working while the runner abstraction settles in.
"""
from __future__ import annotations

from .runners import ScriptResult, get_runner
from .runners.local import ALLOWED_SCRIPTS  # re-exported


class WSLUnavailableError(RuntimeError):
    """Back-compat. Real cause is now runner-specific."""


def run_inline(argv: list[str], *, timeout: int = 60) -> ScriptResult:
    return get_runner().run_inline(argv, timeout=timeout)


def run_script(name: str, args: list[str] | None = None, *, timeout: int = 120) -> ScriptResult:
    return get_runner().run_script(name, args, timeout=timeout)


def read_file(path: str, *, timeout: int = 10) -> str:
    return get_runner().read_file(path, timeout=timeout)


def health_check() -> dict:
    return get_runner().health_check()


__all__ = [
    "ScriptResult",
    "WSLUnavailableError",
    "ALLOWED_SCRIPTS",
    "run_inline",
    "run_script",
    "read_file",
    "health_check",
]
