def test_login_requires_password(client):
    r = client.post("/api/login", json={"password": "wrong"})
    assert r.status_code == 401


def test_login_sets_cookie(client):
    r = client.post("/api/login", json={"password": "test-password"})
    assert r.status_code == 200
    assert "aegis_session" in r.cookies


def test_protected_route_rejects_anon(client):
    r = client.get("/api/scan/processes")
    assert r.status_code == 401


def test_protected_route_accepts_authed(authed_client, monkeypatch):
    from app.routes import scan as scan_route
    monkeypatch.setattr(scan_route, "list_processes", lambda only_flagged=False: [])
    r = authed_client.get("/api/scan/processes")
    assert r.status_code == 200
    assert r.json() == {"processes": []}


def test_health_is_public(client, monkeypatch):
    from app.routes import health as health_route
    monkeypatch.setattr(health_route, "health_check", lambda: {"ok": False, "reason": "test"})
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "wsl" in r.json()
