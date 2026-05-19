"""Tamper-evident audit log tests.

The signer's *live tailer* path is hard to test without WSL, so these focus
on the pure logic: hashing, append, verify, tamper detection. The tailer is
exercised end-to-end during the docker-compose smoke test.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def isolate_signed_path(tmp_path, monkeypatch):
    p = tmp_path / "logs" / "security_audit.signed.jsonl"
    monkeypatch.setattr("app.audit_signer._signed_path", lambda: p)
    yield p


def test_genesis_hash_constant():
    from app.audit_signer import GENESIS_HASH
    assert GENESIS_HASH == "0" * 64


def test_hash_entry_is_deterministic():
    from app.audit_signer import GENESIS_HASH, hash_entry
    a = hash_entry(GENESIS_HASH, 1, "2026-01-01 00:00:00", "INFO", "hi")
    b = hash_entry(GENESIS_HASH, 1, "2026-01-01 00:00:00", "INFO", "hi")
    assert a == b
    c = hash_entry(GENESIS_HASH, 1, "2026-01-01 00:00:00", "INFO", "hello")
    assert a != c


def test_append_chain_links_correctly(isolate_signed_path):
    from app.audit_signer import GENESIS_HASH, append_signed_entry

    r1 = append_signed_entry("2026-01-01 00:00:00", "INFO", "first")
    r2 = append_signed_entry("2026-01-01 00:00:01", "ACTION", "second")
    r3 = append_signed_entry("2026-01-01 00:00:02", "WARN", "third")

    assert r1["seq"] == 1
    assert r1["prev_hash"] == GENESIS_HASH
    assert r2["seq"] == 2
    assert r2["prev_hash"] == r1["entry_hash"]
    assert r3["seq"] == 3
    assert r3["prev_hash"] == r2["entry_hash"]


def test_verify_chain_clean(isolate_signed_path):
    from app.audit_signer import append_signed_entry, verify_chain
    for i in range(5):
        append_signed_entry(f"2026-01-01 00:00:0{i}", "ACTION", f"entry {i}")
    out = verify_chain()
    assert out["ok"] is True
    assert out["total"] == 5
    assert out["first_break_seq"] is None


def test_verify_chain_detects_message_tampering(isolate_signed_path):
    from app.audit_signer import append_signed_entry, verify_chain
    for i in range(3):
        append_signed_entry(f"2026-01-01 00:00:0{i}", "ACTION", f"entry {i}")

    # Tamper: rewrite entry #2's message without recomputing hashes
    lines = isolate_signed_path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[1])
    obj["message"] = "evil rewrite"
    lines[1] = json.dumps(obj)
    isolate_signed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = verify_chain()
    assert out["ok"] is False
    assert out["first_break_seq"] == 2
    assert "entry_hash" in out["first_break_reason"]


def test_verify_chain_detects_inserted_row(isolate_signed_path):
    from app.audit_signer import append_signed_entry, verify_chain
    for i in range(3):
        append_signed_entry(f"2026-01-01 00:00:0{i}", "ACTION", f"entry {i}")
    # Insert a fake row between #1 and #2 — its prev_hash won't match #1
    lines = isolate_signed_path.read_text(encoding="utf-8").splitlines()
    fake = {
        "seq": 2, "ts": "2026-01-01 00:00:99", "level": "ACTION",
        "message": "back-dated insert",
        "prev_hash": "0" * 64, "entry_hash": "f" * 64,
    }
    lines.insert(1, json.dumps(fake))
    isolate_signed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = verify_chain()
    assert out["ok"] is False
    assert out["first_break_seq"] == 2


def test_verify_empty_ledger_is_ok(isolate_signed_path):
    from app.audit_signer import verify_chain
    out = verify_chain()
    assert out == {"ok": True, "total": 0, "first_break_seq": None, "first_break_reason": None}


def test_resume_continues_from_last_seq(isolate_signed_path):
    """If the signer is restarted, new appends pick up where it left off."""
    from app.audit_signer import _last_signed, append_signed_entry
    append_signed_entry("2026-01-01 00:00:00", "INFO", "a")
    append_signed_entry("2026-01-01 00:00:01", "INFO", "b")
    seq, prev = _last_signed()
    assert seq == 2
    # Simulate restart: import again, append should continue
    r = append_signed_entry("2026-01-01 00:00:02", "INFO", "c")
    assert r["seq"] == 3
    assert r["prev_hash"] == prev


def test_verify_route_requires_auth(client):
    r = client.get("/api/audit/verify")
    assert r.status_code == 401


def test_verify_route_returns_status(authed_client, isolate_signed_path):
    from app.audit_signer import append_signed_entry
    append_signed_entry("2026-01-01 00:00:00", "INFO", "x")
    r = authed_client.get("/api/audit/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["total"] == 1


# ---------- CLI ----------

def test_cli_verify_audit_clean(isolate_signed_path, capsys):
    from app.audit_signer import append_signed_entry
    from app.cli import main
    append_signed_entry("2026-01-01 00:00:00", "INFO", "x")
    rc = main(["verify-audit"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "intact" in out


def test_cli_verify_audit_detects_tamper(isolate_signed_path, capsys):
    from app.audit_signer import append_signed_entry
    from app.cli import main
    append_signed_entry("2026-01-01 00:00:00", "INFO", "x")
    # Corrupt
    lines = isolate_signed_path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[0])
    obj["message"] = "hacked"
    isolate_signed_path.write_text(json.dumps(obj) + "\n", encoding="utf-8")
    rc = main(["verify-audit"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "Tampering" in out
