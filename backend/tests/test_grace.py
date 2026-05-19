"""Grace state-machine + route tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


@pytest.fixture
def fake_notifier(monkeypatch):
    from app.notifiers.base import NullNotifier
    from app.notifiers import factory
    n = NullNotifier()
    factory.reset_notifier_cache()
    monkeypatch.setattr(factory, "_cached", n)
    yield n
    factory.reset_notifier_cache()


@pytest.fixture
def fake_policy(monkeypatch):
    from app.policy import loader
    from app.policy.loader import UserPolicy
    pol = UserPolicy(by_user={"alice": {"slack_id": "U_ALICE"}}, default_slack_id="U_ADMIN")
    monkeypatch.setattr(loader, "_cached", pol)
    monkeypatch.setattr("app.grace.policy", lambda: pol)
    yield pol


@pytest.fixture(autouse=True)
def silence_audit(monkeypatch):
    monkeypatch.setattr("app.grace.append_audit", lambda *_a, **_k: None)


def test_create_warning_sends_notification_and_stores(fake_notifier, fake_policy):
    from app.grace import create_warning, get_warning
    w = create_warning(
        target_kind="kill",
        target_payload={"pid": 4821},
        owner_linux_user="alice",
        reason="cpu 95%",
        grace_minutes=30,
    )
    assert w["status"] == "sent"
    assert w["owner_slack_id"] == "U_ALICE"
    assert len(fake_notifier.sent) == 1
    assert "PID 4821" in fake_notifier.sent[0]["action_summary"]
    assert fake_notifier.sent[0]["ack_url"].endswith(w["ack_token"])
    again = get_warning(w["id"])
    assert again["ack_token"] == w["ack_token"]


def test_create_warning_uses_default_user_slack(fake_notifier, fake_policy):
    from app.grace import create_warning
    w = create_warning(
        target_kind="kill",
        target_payload={"pid": 9999},
        owner_linux_user="randomstudent",  # not in map
        reason="overnight",
    )
    assert w["owner_slack_id"] == "U_ADMIN"


def test_acknowledge_stop_flips_status(fake_notifier, fake_policy):
    from app.grace import acknowledge, create_warning
    w = create_warning(
        target_kind="kill",
        target_payload={"pid": 1}, owner_linux_user="alice", reason="x",
    )
    out = acknowledge(w["ack_token"], action="stop", reason="please wait 6h")
    assert out["status"] == "stop"
    assert out["ack_action"] == "stop"
    assert out["ack_reason"] == "please wait 6h"


def test_acknowledge_explain_flips_status(fake_notifier, fake_policy):
    from app.grace import acknowledge, create_warning
    w = create_warning(target_kind="kill", target_payload={"pid": 1}, owner_linux_user="alice", reason="x")
    out = acknowledge(w["ack_token"], action="explain", reason="gpu benchmark")
    assert out["status"] == "explained"


def test_acknowledge_idempotent(fake_notifier, fake_policy):
    from app.grace import acknowledge, create_warning
    w = create_warning(target_kind="kill", target_payload={"pid": 1}, owner_linux_user="alice", reason="x")
    acknowledge(w["ack_token"], action="stop")
    out = acknowledge(w["ack_token"], action="explain")  # second click — should NOT overwrite
    assert out["status"] == "stop"


def test_expire_overdue_escalates_to_gate(fake_notifier, fake_policy):
    from app.db import conn
    from app.gates import list_gates
    from app.grace import create_warning, expire_overdue, get_warning

    w = create_warning(target_kind="kill", target_payload={"pid": 1}, owner_linux_user="alice", reason="x")
    # Force the warning to be expired
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
    conn().execute("UPDATE grace_warnings SET expires_at=? WHERE id=?", (past, w["id"]))

    out = expire_overdue()
    assert len(out) == 1
    refreshed = get_warning(w["id"])
    assert refreshed["status"] == "escalated"
    assert refreshed["escalated_gate_id"] is not None

    # Inspect the gate the sweeper created
    gate = next(g for g in list_gates() if g["id"] == refreshed["escalated_gate_id"])
    assert gate["kind"] == "kill"
    assert gate["payload"]["pid"] == 1
    assert gate["payload"]["grace_warning_id"] == w["id"]
    assert gate["origin"] == "grace_expiry"


def test_expire_overdue_skips_acknowledged(fake_notifier, fake_policy):
    from app.grace import acknowledge, create_warning, expire_overdue
    w = create_warning(target_kind="kill", target_payload={"pid": 1}, owner_linux_user="alice", reason="x")
    acknowledge(w["ack_token"], action="explain", reason="ok")
    with patch("app.grace.create_gate") as mock_create:
        out = expire_overdue()
    mock_create.assert_not_called()
    assert out == []


# ---------- Route tests ----------

def test_warn_then_kill_route_creates_warning(authed_client, fake_notifier, fake_policy, monkeypatch):
    from app.routes import act as act_route
    from app.scripts.models import ProcessRow
    monkeypatch.setattr(
        act_route, "list_processes",
        lambda only_flagged=False: [ProcessRow(
            pid=4821, user="alice", cpuPct=95.0, memPct=12.0,
            runtimeSeconds=99999, command="train.py", state="R",
            flagged=True, reasons=["cpu"],
        )],
    )
    r = authed_client.post("/api/act/kill", json={
        "pid": 4821, "reason": "long runtime", "mode": "warn_then_kill",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["owner"] == "alice"
    assert body["channel"] == "null"  # fake_notifier
    assert "warning_id" in body
    assert len(fake_notifier.sent) == 1


def test_immediate_mode_creates_gate_not_warning(authed_client, fake_notifier, fake_policy):
    r = authed_client.post("/api/act/kill", json={"pid": 1234, "reason": "test", "mode": "immediate"})
    assert r.status_code == 200
    assert "gate_id" in r.json()
    assert len(fake_notifier.sent) == 0


def test_ack_landing_unknown_token_404(client):
    r = client.get("/api/grace/ack/totallyfakeXYZ")
    assert r.status_code == 404


def test_ack_landing_renders_form_for_open_warning(client, fake_notifier, fake_policy):
    from app.grace import create_warning
    w = create_warning(target_kind="kill", target_payload={"pid": 7}, owner_linux_user="alice", reason="x")
    r = client.get(f"/api/grace/ack/{w['ack_token']}")
    assert r.status_code == 200
    assert "STOP" in r.text
    assert "KEEP" in r.text


def test_ack_post_records_decision(client, fake_notifier, fake_policy):
    from app.grace import create_warning, get_warning
    w = create_warning(target_kind="kill", target_payload={"pid": 7}, owner_linux_user="alice", reason="x")
    r = client.post(
        f"/api/grace/ack/{w['ack_token']}",
        data={"action": "explain", "reason": "gpu bench"},
    )
    assert r.status_code == 200
    after = get_warning(w["id"])
    assert after["status"] == "explained"
    assert after["ack_reason"] == "gpu bench"


def test_ack_post_rejects_bad_action(client, fake_notifier, fake_policy):
    from app.grace import create_warning
    w = create_warning(target_kind="kill", target_payload={"pid": 7}, owner_linux_user="alice", reason="x")
    r = client.post(f"/api/grace/ack/{w['ack_token']}", data={"action": "rm-rf"})
    assert r.status_code == 400


def test_admin_list_warnings_requires_auth(client, fake_notifier, fake_policy):
    from app.grace import create_warning
    create_warning(target_kind="kill", target_payload={"pid": 7}, owner_linux_user="alice", reason="x")
    r = client.get("/api/grace")
    assert r.status_code == 401


def test_admin_list_warnings(authed_client, fake_notifier, fake_policy):
    from app.grace import create_warning
    create_warning(target_kind="kill", target_payload={"pid": 7}, owner_linux_user="alice", reason="x")
    r = authed_client.get("/api/grace")
    assert r.status_code == 200
    assert len(r.json()["warnings"]) >= 1
