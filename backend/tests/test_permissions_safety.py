import pytest

from app.scripts.permissions import _safe_path


def test_safe_path_accepts_normal_absolute():
    assert _safe_path("/home/alice/file.txt") == "/home/alice/file.txt"


def test_safe_path_rejects_relative():
    with pytest.raises(ValueError):
        _safe_path("home/alice/file.txt")


def test_safe_path_rejects_parent_traversal():
    with pytest.raises(ValueError):
        _safe_path("/home/alice/../../etc/passwd")


def test_safe_path_rejects_metacharacters():
    for bad in ["/tmp/foo;rm", "/tmp/foo$x", "/tmp/foo`x`", "/tmp/foo|x", "/tmp/foo\nx"]:
        with pytest.raises(ValueError):
            _safe_path(bad)
