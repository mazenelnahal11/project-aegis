from app import wsl_bridge


def test_run_script_rejects_unknown_name():
    import pytest
    with pytest.raises(ValueError):
        wsl_bridge.run_script("not_a_real_script")


def test_run_script_accepts_allowlisted_names(monkeypatch):
    captured = {}

    def fake_run(argv, *, capture_output, text, timeout, check):
        captured["argv"] = argv
        class R:
            stdout = ""
            stderr = ""
            returncode = 0
        return R()

    monkeypatch.setattr(wsl_bridge.subprocess, "run", fake_run)
    monkeypatch.setattr(wsl_bridge.shutil, "which", lambda _: "wsl.exe")

    res = wsl_bridge.run_script("1_process_hunter")
    assert res.ok
    assert "1_process_hunter.sh" in " ".join(captured["argv"])
    assert "wsl.exe" in captured["argv"][0]
