from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class ScriptResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Runner(Protocol):
    """Shell-execution backend.

    Two implementations: `LocalRunner` (Linux/macOS, direct subprocess) and
    `WSLRunner` (Windows host shelling into a WSL distro). The interface is
    intentionally minimal — argv only, no shell strings, so injection is
    impossible at this layer.
    """

    name: str

    def run_inline(self, argv: list[str], *, timeout: int = 60) -> ScriptResult: ...
    def run_script(self, name: str, args: list[str] | None = None, *, timeout: int = 120) -> ScriptResult: ...
    def write_file_append(self, path: str, content: str, *, timeout: int = 5) -> None: ...
    def read_file(self, path: str, *, timeout: int = 10) -> str: ...
    def health_check(self) -> dict: ...

    async def tail_follow(self, path: str) -> AsyncIterator[str]:  # type: ignore[override]
        """Yield each new line appended to `path` (`tail -n 0 -F` semantics)."""
        ...
