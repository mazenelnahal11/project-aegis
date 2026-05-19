"""Tests for the propose_warn_then_kill tool path."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def silence_audit_grace(monkeypatch):
    monkeypatch.setattr("app.grace.append_audit", lambda *_a, **_k: None)


def test_propose_warn_then_kill_creates_gate_not_warning():
    """The LLM tool must create a *pending gate*, not directly create a
    grace warning. Only after the admin approves the gate should the Slack
    DM go out — same invariant as everything else destructive.
    """
    from app.gates import get_gate, list_gates
    from app.grace import list_warnings
    from app.llm.executor import execute_tool

    out = execute_tool(
        "propose_warn_then_kill",
        {"pid": 4821, "reason": "27h runtime, 92% CPU", "grace_minutes": 15},
        chat_session_id="s1",
        tool_use_id="tu_warn",
    )
    assert out["requires_confirmation"] is True
    assert out["executed"] is False
    assert out["kind"] == "warn_then_kill"
    g = get_gate(out["gate_id"])
    assert g["status"] == "pending"
    assert g["kind"] == "warn_then_kill"
    assert g["payload"]["pid"] == 4821
    assert g["payload"]["grace_minutes"] == 15
    # No grace warning yet — the gate is only a *proposal*.
    assert list_warnings() == []


def test_approving_warn_gate_sends_slack_dm(monkeypatch):
    from app.gates import approve_and_execute, create_gate
    from app.grace import list_warnings
    from app.notifiers import factory
    from app.notifiers.base import NullNotifier
    from app.policy import loader
    from app.policy.loader import UserPolicy
    from app.scripts.models import ProcessRow

    # Wire up a fake notifier + policy
    pol = UserPolicy(by_user={"alice": {"slack_id": "U_ALICE"}}, default_slack_id="U_ADMIN")
    monkeypatch.setattr(loader, "_cached", pol)
    monkeypatch.setattr("app.grace.policy", lambda: pol)
    n = NullNotifier()
    factory.reset_notifier_cache()
    monkeypatch.setattr(factory, "_cached", n)

    # And the gate executor needs list_processes to find the owner of PID 4821
    monkeypatch.setattr(
        "app.scripts.process_hunter.list_processes",
        lambda only_flagged=False: [ProcessRow(
            pid=4821, user="alice", cpuPct=92.0, memPct=10.0,
            runtimeSeconds=99999, command="train.py", state="R",
            flagged=True, reasons=["cpu"],
        )],
    )

    gate = create_gate(
        kind="warn_then_kill",
        payload={"pid": 4821, "reason": "long runtime", "grace_minutes": 15},
        origin="llm",
    )
    out = approve_and_execute(gate["id"])
    assert out["status"] == "executed"
    assert out["result"]["owner"] == "alice"
    assert out["result"]["channel"] == "null"
    # Now a grace warning *does* exist, with the DM having gone out
    warnings = list_warnings()
    assert len(warnings) == 1
    assert warnings[0]["target_kind"] == "kill"
    assert warnings[0]["target_payload"]["pid"] == 4821
    assert warnings[0]["origin"] == "llm"
    assert len(n.sent) == 1
    factory.reset_notifier_cache()
