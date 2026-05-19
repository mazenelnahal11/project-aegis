"""Runner abstraction tests. WSL runner only checks the argv shape via mocks;
the live behavior is exercised in the existing test_wsl_bridge.py."""
from __future__ import annotations



def test_factory_picks_local_on_non_windows(monkeypatch, tmp_path):
    from app.runners import factory
    monkeypatch.setenv("AEGIS_RUNNER", "local")
    monkeypatch.setenv("AEGIS_PROJECT_DIR", str(tmp_path))
    factory.reset_runner_cache()
    r = factory.get_runner()
    assert r.name == "local"
    factory.reset_runner_cache()


def test_factory_picks_wsl(monkeypatch):
    from app.runners import factory
    monkeypatch.setenv("AEGIS_RUNNER", "wsl")
    factory.reset_runner_cache()
    r = factory.get_runner()
    assert r.name == "wsl"
    factory.reset_runner_cache()


def test_local_runner_runs_simple_command(tmp_path):
    from app.runners.local import LocalRunner
    r = LocalRunner(project_dir=tmp_path)
    res = r.run_inline(["python", "-c", "print('hi')"])
    assert res.ok
    assert "hi" in res.stdout


def test_local_runner_rejects_unknown_script(tmp_path):
    from app.runners.local import LocalRunner
    import pytest
    r = LocalRunner(project_dir=tmp_path)
    with pytest.raises(ValueError):
        r.run_script("not_a_real_script")


def test_local_runner_append_and_read(tmp_path):
    from app.runners.local import LocalRunner
    r = LocalRunner(project_dir=tmp_path)
    p = tmp_path / "logs" / "x.log"
    r.write_file_append(str(p), "first\n")
    r.write_file_append(str(p), "second\n")
    out = r.read_file(str(p))
    assert out == "first\nsecond\n"
    # Reading a missing file is empty, not an error
    assert r.read_file(str(tmp_path / "missing.log")) == ""


def test_local_runner_health_check(tmp_path):
    from app.runners.local import LocalRunner
    r = LocalRunner(project_dir=tmp_path)
    h = r.health_check()
    assert h["ok"] is True
    assert h["kind"] == "local"
    assert "platform" in h


def test_wsl_runner_argv_shape(monkeypatch):
    from app.runners.wsl import WSLRunner

    captured = {}
    class R:
        stdout = ""
        stderr = ""
        returncode = 0
    def fake_run(argv, capture_output, text, timeout, check):
        captured["argv"] = argv
        return R()

    monkeypatch.setattr("app.runners.wsl.shutil.which", lambda _: "wsl.exe")
    monkeypatch.setattr("app.runners.wsl.subprocess.run", fake_run)

    r = WSLRunner(distro="Ubuntu", project_dir_wsl="/mnt/c/aegis")
    out = r.run_script("1_process_hunter")
    assert out.ok
    assert captured["argv"][:4] == ["wsl.exe", "-d", "Ubuntu", "--"]
    assert "1_process_hunter.sh" in captured["argv"][-1]
