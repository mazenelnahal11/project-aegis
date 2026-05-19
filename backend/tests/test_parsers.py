from app.scripts.process_hunter import _parse_ps, _apply_flagging, parse_rogue_log_lines


def test_parse_ps_basic():
    raw = (
        "  123 alice                          5.0  1.2  3600 R    python\n"
        " 4567 bob                           95.0  2.4  90000 S    train.py\n"
        "    8 root                           0.0  0.0    10 S    kthreadd\n"
    )
    rows = _parse_ps(raw)
    assert len(rows) == 3
    assert rows[0].pid == 123 and rows[0].user == "alice" and rows[0].command == "python"
    assert rows[1].cpu_pct == 95.0 and rows[1].runtime_seconds == 90000


def test_apply_flagging_thresholds():
    rows = _parse_ps(
        "  1 alice 90.0 1.0 100 R python\n"
        "  2 bob 5.0 1.0 90000 S train.py\n"
        "  3 root 99.0 1.0 99999 R kthreadd\n"
        "  4 carol 5.0 1.0 100 Z zombie_proc\n"
    )
    _apply_flagging(rows)
    flagged = {r.pid: r for r in rows if r.flagged}
    assert 1 in flagged  # cpu over limit
    assert 2 in flagged  # runtime over limit
    assert 3 not in flagged  # root excluded
    assert 4 in flagged  # zombie state


def test_parse_rogue_log_lines():
    log = (
        "[2026-05-19 12:00:00] [WARN] ROGUE PROCESS | PID=4821 | USER=alice | CMD=train.py | "
        "Runtime=72h (>= 24h) | CPU=82% (>= 80%) | MEM=12.3%\n"
        "[2026-05-19 12:00:01] [INFO] === something else ===\n"
    )
    parsed = parse_rogue_log_lines(log)
    assert len(parsed) == 1
    assert parsed[0]["pid"] == "4821"
    assert parsed[0]["user"] == "alice"
