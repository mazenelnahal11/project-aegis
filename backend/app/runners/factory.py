"""Auto-pick a runner.

Default policy:
  - `AEGIS_RUNNER=local`       → LocalRunner against AEGIS_PROJECT_DIR
  - `AEGIS_RUNNER=wsl`         → WSLRunner against AEGIS_PROJECT_DIR_WSL
  - unset → `local` on Linux/macOS, `wsl` on Windows.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from ..config import settings
from .base import Runner

_cached: Runner | None = None


def _auto_kind() -> str:
    if sys.platform == "win32":
        return "wsl"
    return "local"


def get_runner() -> Runner:
    global _cached
    if _cached is not None:
        return _cached
    kind = (os.environ.get("AEGIS_RUNNER") or _auto_kind()).lower()
    if kind == "local":
        from .local import LocalRunner
        # When running inside the Docker container, AEGIS_PROJECT_DIR is set
        # to /app; on a Linux host you can override it. Default: the repo
        # root inferred from this file.
        project_dir = os.environ.get("AEGIS_PROJECT_DIR") or str(
            Path(__file__).resolve().parents[3]
        )
        _cached = LocalRunner(project_dir=project_dir)
    elif kind == "wsl":
        from .wsl import WSLRunner
        _cached = WSLRunner(
            distro=settings.wsl_distro,
            project_dir_wsl=settings.project_dir_wsl,
        )
    else:
        raise RuntimeError(f"unknown AEGIS_RUNNER: {kind!r}")
    return _cached


def reset_runner_cache() -> None:
    global _cached
    _cached = None
