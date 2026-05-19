"""WSLRunner — shells from Windows into a WSL distro. Convenience for the
developer machine; the Docker demo and any real Linux deployment use
LocalRunner instead.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import AsyncIterator

from .base import ScriptResult
from .local import ALLOWED_SCRIPTS


class WSLUnavailableError(RuntimeError):
    pass


class WSLRunner:
    name = "wsl"

    def __init__(self, distro: str, project_dir_wsl: str):
        self.distro = distro
        self.project_dir_wsl = project_dir_wsl

    def _wsl(self) -> str:
        exe = shutil.which("wsl.exe") or shutil.which("wsl")
        if not exe:
            raise WSLUnavailableError("wsl.exe not found on PATH")
        return exe

    def run_inline(self, argv: list[str], *, timeout: int = 60) -> ScriptResult:
        exe = self._wsl()
        proc = subprocess.run(
            [exe, "-d", self.distro, "--", *argv],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        return ScriptResult(stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode)

    def run_script(self, name: str, args: list[str] | None = None, *, timeout: int = 120) -> ScriptResult:
        if name not in ALLOWED_SCRIPTS:
            raise ValueError(f"script '{name}' is not in the allowlist")
        path = f"{self.project_dir_wsl}/scripts/{name}.sh"
        return self.run_inline(["bash", path, *(args or [])], timeout=timeout)

    def write_file_append(self, path: str, content: str, *, timeout: int = 5) -> None:
        exe = self._wsl()
        # tee -a via stdin avoids shell-redirection / interpolation.
        self.run_inline(["mkdir", "-p", path.rsplit("/", 1)[0]], timeout=timeout)
        subprocess.run(
            [exe, "-d", self.distro, "--", "tee", "-a", path],
            input=content, text=True, capture_output=True,
            timeout=timeout, check=False,
        )

    def read_file(self, path: str, *, timeout: int = 10) -> str:
        return self.run_inline(["cat", path], timeout=timeout).stdout

    def health_check(self) -> dict:
        try:
            exe = self._wsl()
        except WSLUnavailableError as e:
            return {"ok": False, "kind": "wsl", "reason": str(e)}
        proc = subprocess.run(
            [exe, "-l", "-q"], capture_output=True, text=True, timeout=10,
        )
        distros = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if self.distro not in distros:
            return {"ok": False, "kind": "wsl",
                    "reason": f"distro {self.distro!r} not installed",
                    "available": distros}
        probe = self.run_inline(["uname", "-s"], timeout=10)
        if not probe.ok:
            return {"ok": False, "kind": "wsl",
                    "reason": f"probe failed: {probe.stderr.strip()}"}
        return {"ok": True, "kind": "wsl", "distro": self.distro,
                "kernel": probe.stdout.strip()}

    async def tail_follow(self, path: str) -> AsyncIterator[str]:
        exe = self._wsl()
        proc = await asyncio.create_subprocess_exec(
            exe, "-d", self.distro, "--", "tail", "-n", "0", "-F", path,
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
