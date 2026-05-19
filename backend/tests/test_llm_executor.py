from unittest.mock import patch

from app.llm.executor import execute_tool


def test_read_only_tool_runs_immediately():
    with patch("app.llm.executor.list_processes", return_value=[]) as mock_lp:
        out = execute_tool(
            "list_processes",
            {"only_flagged": True, "limit": 10},
            chat_session_id="s1",
            tool_use_id="tu_1",
        )
    mock_lp.assert_called_once_with(only_flagged=True)
    assert out == {"processes": []}


def test_propose_kill_creates_gate_does_not_execute():
    out = execute_tool(
        "propose_kill_process",
        {"pid": 9999, "reason": "runaway training loop"},
        chat_session_id="s1",
        tool_use_id="tu_kill",
    )
    assert out["requires_confirmation"] is True
    assert out["executed"] is False
    assert isinstance(out["gate_id"], int)

    from app.gates import get_gate
    g = get_gate(out["gate_id"])
    assert g["status"] == "pending"
    assert g["origin"] == "llm"
    assert g["tool_use_id"] == "tu_kill"


def test_propose_fix_permission_creates_gate():
    out = execute_tool(
        "propose_fix_permission",
        {"path": "/home/alice/secret.txt", "mode": "644", "reason": "world-writable secret"},
        chat_session_id="s1",
        tool_use_id="tu_fix",
    )
    assert out["requires_confirmation"] is True
    assert out["executed"] is False
    from app.gates import get_gate
    g = get_gate(out["gate_id"])
    assert g["kind"] == "fix_permission"
    assert g["payload"]["mode"] == "644"


def test_unknown_tool_returns_error():
    out = execute_tool("delete_etc_passwd", {}, chat_session_id=None, tool_use_id="x")
    assert "error" in out
