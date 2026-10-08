from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


def test_local_account_login_and_password_update(initialized_db_session):
    def override_db():
        yield initialized_db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        assert client.get("/api/auth/session").json()["data"] == {"authenticated": False, "username": None}
        assert client.post("/api/auth/login", json={"username": "xp", "password": "wrong"}).status_code == 401
        assert client.post("/api/auth/login", json={"username": "xp", "password": "980127"}).json()["data"] == {"username": "xp"}
        changed = client.put("/api/auth/credentials", json={"username": "xp-invest", "current_password": "980127", "new_password": "new-pass"})
        assert changed.status_code == 200
        assert changed.json()["data"] == {"username": "xp-invest"}
        client.post("/api/auth/logout")
        assert client.post("/api/auth/login", json={"username": "xp", "password": "980127"}).status_code == 401
        assert client.post("/api/auth/login", json={"username": "xp-invest", "password": "new-pass"}).status_code == 200
    finally:
        app.dependency_overrides.clear()
