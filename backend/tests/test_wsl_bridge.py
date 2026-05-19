"""Smoke tests for the wsl_bridge back-compat shim. The real coverage lives
in test_runners.py now.
"""
from app import wsl_bridge


def test_run_script_rejects_unknown_name(monkeypatch):
    # Force the shim to talk to a WSL runner so the allowlist applies the
    # same way it did before the refactor.
    from app.runners import factory
    from app.runners.wsl import WSLRunner
    monkeypatch.setattr(factory, "_cached", WSLRunner(distro="x", project_dir_wsl="/x"))
    import pytest
    with pytest.raises(ValueError):
        wsl_bridge.run_script("not_a_real_script")
    factory.reset_runner_cache()


def test_run_script_argv_via_shim(monkeypatch):
    """Calling the shim should hit whatever runner the factory picks."""
    from app.runners import factory, wsl as wsl_runner
    monkeypatch.setattr(wsl_runner.shutil, "which", lambda _: "wsl.exe")

    captured = {}
    class R:
        stdout = ""
        stderr = ""
        returncode = 0
    def fake_run(argv, capture_output, text, timeout, check):
        captured["argv"] = argv
        return R()
    monkeypatch.setattr(wsl_runner.subprocess, "run", fake_run)

    monkeypatch.setattr(
        factory, "_cached",
        wsl_runner.WSLRunner(distro="Ubuntu", project_dir_wsl="/mnt/c/aegis"),
    )
    res = wsl_bridge.run_script("1_process_hunter")
    assert res.ok
    assert "1_process_hunter.sh" in captured["argv"][-1]
    assert captured["argv"][:4] == ["wsl.exe", "-d", "Ubuntu", "--"]
    factory.reset_runner_cache()
