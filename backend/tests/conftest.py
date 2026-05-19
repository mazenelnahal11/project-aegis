import os

import bcrypt
import pytest

os.environ["AEGIS_ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(
    b"test-password", bcrypt.gensalt()
).decode("ascii")
os.environ["AEGIS_JWT_SECRET"] = "test-secret-test-secret-test-secret"
os.environ["AEGIS_ANTHROPIC_API_KEY"] = ""  # disable llm route by default
os.environ["AEGIS_WSL_DISTRO"] = "test-distro"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "aegis-test.db"
    from app import config, db as db_mod
    monkeypatch.setattr(config.settings, "db_path", db_path)
    db_mod._conn = None
    db_mod.init_db()
    yield db_path
    db_mod._conn = None


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import create_app
    return TestClient(create_app())


@pytest.fixture
def authed_client(client):
    r = client.post("/api/login", json={"password": "test-password"})
    assert r.status_code == 200, r.text
    return client
