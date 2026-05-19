from unittest.mock import patch

from app.gates import approve_and_execute, create_gate, get_gate, list_gates, reject_gate


def test_create_and_list_gate():
    g = create_gate(kind="kill", payload={"pid": 1234}, origin="ui")
    assert g["status"] == "pending"
    listed = list_gates()
    assert any(x["id"] == g["id"] for x in listed)


def test_reject_gate_marks_status():
    g = create_gate(kind="kill", payload={"pid": 1234}, origin="ui")
    r = reject_gate(g["id"])
    assert r["status"] == "rejected"


def test_approve_kill_calls_terminator():
    g = create_gate(kind="kill", payload={"pid": 4321}, origin="ui")
    fake_result = {"pid": 4321, "outcome": "sigterm_clean"}
    with patch("app.gates.terminate_pid", return_value=fake_result) as mock_term:
        out = approve_and_execute(g["id"])
    mock_term.assert_called_once_with(4321)
    assert out["status"] == "executed"
    assert out["result"]["outcome"] == "sigterm_clean"


def test_approve_fix_permission_dispatches():
    g = create_gate(
        kind="fix_permission",
        payload={"path": "/tmp/x", "mode": "644"},
        origin="ui",
    )
    fake = {"path": "/tmp/x", "outcome": "fixed", "owner": "alice", "type": "file", "new_mode": "644"}
    with patch("app.gates.fix_permission", return_value=fake) as mock_fix:
        out = approve_and_execute(g["id"])
    mock_fix.assert_called_once_with("/tmp/x", "644")
    assert out["status"] == "executed"


def test_approve_idempotent_after_execution():
    g = create_gate(kind="kill", payload={"pid": 1}, origin="ui")
    with patch("app.gates.terminate_pid", return_value={"pid": 1, "outcome": "sigterm_clean"}):
        approve_and_execute(g["id"])
    # second approve is a no-op
    out2 = approve_and_execute(g["id"])
    assert out2["status"] == "executed"
