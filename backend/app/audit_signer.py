"""Append-only, hash-chained ledger of `security_audit.log`.

Each line of the bash audit log gets mirrored to a signed JSONL file:

    {"seq": 42, "ts": "...", "level": "...", "message": "...",
     "prev_hash": "<sha256 hex>", "entry_hash": "<sha256 hex>"}

`entry_hash = sha256(prev_hash + "\n" + canonical_json(seq, ts, level, message))`

Genesis prev_hash is 64 zeros. The signer tails the bash log via the existing
WSL bridge (`tail -F`), so it survives log rotation and starts cheap.

Resume semantics: on startup we read the last signed line's `seq` and skip
forward in the bash log by that many *parsed* (timestamp-bearing) lines.
This is intentionally simple — for the demo's volumes (thousands of lines)
it's instant.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterator

from .config import settings

log = logging.getLogger("aegis.audit_signer")

GENESIS_HASH = "0" * 64

_AUDIT_RE = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+\[(?P<level>[A-Z]+)\]\s+(?P<msg>.*)$")


def _signed_path() -> Path:
    return Path(__file__).resolve().parent.parent / "logs" / "security_audit.signed.jsonl"


def _bash_log_wsl_path() -> str:
    return f"{settings.project_dir_wsl}/logs/security_audit.log"


def _canonical(seq: int, ts: str, level: str, message: str) -> str:
    return json.dumps(
        {"seq": seq, "ts": ts, "level": level, "message": message},
        sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    )


def hash_entry(prev_hash: str, seq: int, ts: str, level: str, message: str) -> str:
    blob = prev_hash + "\n" + _canonical(seq, ts, level, message)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _last_signed() -> tuple[int, str]:
    """Return (last_seq, last_hash). (0, GENESIS_HASH) if file empty/missing."""
    p = _signed_path()
    if not p.exists() or p.stat().st_size == 0:
        return 0, GENESIS_HASH
    last_line = ""
    with p.open("rb") as f:
        # Cheap tail: read from end and walk back a few KB
        try:
            f.seek(-4096, 2)
        except OSError:
            f.seek(0)
        chunk = f.read().decode("utf-8", errors="replace")
        for line in chunk.splitlines():
            if line.strip():
                last_line = line
    if not last_line:
        return 0, GENESIS_HASH
    try:
        obj = json.loads(last_line)
        return int(obj["seq"]), str(obj["entry_hash"])
    except (json.JSONDecodeError, KeyError, ValueError):
        # Partial write; treat as empty (caller will re-append).
        log.warning("signed ledger has trailing garbage; will overwrite")
        return 0, GENESIS_HASH


def append_signed_entry(ts: str, level: str, message: str) -> dict:
    """Append one signed entry. Returns the new record."""
    p = _signed_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    seq, prev_hash = _last_signed()
    new_seq = seq + 1
    entry_hash = hash_entry(prev_hash, new_seq, ts, level, message)
    record = {
        "seq": new_seq, "ts": ts, "level": level, "message": message,
        "prev_hash": prev_hash, "entry_hash": entry_hash,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        try:
            import os
            os.fsync(f.fileno())
        except OSError:
            pass
    return record


def iter_signed() -> Iterator[dict]:
    p = _signed_path()
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Trailing partial line — stop here (verifier will flag it).
                break


def verify_chain() -> dict:
    """Walk the signed ledger and recompute every hash.

    Returns:
      {ok: bool, total: int, first_break_seq: int|None, first_break_reason: str|None}
    """
    prev = GENESIS_HASH
    total = 0
    for rec in iter_signed():
        total += 1
        seq = rec.get("seq")
        if seq != total:
            return {"ok": False, "total": total, "first_break_seq": total,
                    "first_break_reason": f"sequence gap: expected {total}, got {seq}"}
        expected_prev = prev
        if rec.get("prev_hash") != expected_prev:
            return {"ok": False, "total": total, "first_break_seq": seq,
                    "first_break_reason": "prev_hash mismatch"}
        recomputed = hash_entry(
            expected_prev, int(rec["seq"]), rec["ts"], rec["level"], rec["message"],
        )
        if recomputed != rec.get("entry_hash"):
            return {"ok": False, "total": total, "first_break_seq": seq,
                    "first_break_reason": "entry_hash mismatch (message or metadata altered)"}
        prev = rec["entry_hash"]
    return {"ok": True, "total": total, "first_break_seq": None, "first_break_reason": None}


# ----------- Live tailer (background task in lifespan) -----------

async def run_signer() -> None:
    """Long-running coroutine: tail the bash log and append signed entries.

    Tolerates WSL not being available (no-op until it comes back).
    """
    while True:
        try:
            await _tail_once()
        except Exception:
            log.exception("audit signer crashed; restarting in 5s")
        await asyncio.sleep(5)


async def _tail_once() -> None:
    exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if not exe:
        await asyncio.sleep(60)
        return

    # `tail -n +1 -F` starts at the beginning and follows. We dedupe by maintaining
    # a count of *parsed* lines we've already signed.
    skip = sum(1 for _ in iter_signed())
    proc = await asyncio.create_subprocess_exec(
        exe, "-d", settings.wsl_distro, "--",
        "tail", "-n", "+1", "-F", _bash_log_wsl_path(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    try:
        assert proc.stdout is not None
        parsed = 0
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            m = _AUDIT_RE.match(line)
            if not m:
                continue
            parsed += 1
            if parsed <= skip:
                continue
            await asyncio.to_thread(
                append_signed_entry, m.group("ts"), m.group("level"), m.group("msg"),
            )
    finally:
        try:
            proc.terminate()
            await proc.wait()
        except ProcessLookupError:
            pass
