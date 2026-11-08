from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_api_key
from app.api.v1 import auth as routes
from app.core.config import get_settings
from app.core.database import get_db
from app.core.passwords import hash_password, verify_password
from app.core.rate_limit import RateLimiter
from app.services.session_service import SessionService, digest


@pytest.fixture
def browser(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "browser_username", "owner")
    monkeypatch.setattr(settings, "browser_password_hash", hash_password("a sufficiently long test password"))
    monkeypatch.setattr(routes, "login_limiter", RateLimiter(5))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db

    @app.post("/api/v1/probe", dependencies=[Depends(require_api_key)])
    def probe():
        return {"ok": True}

    return TestClient(app), settings


def login(client, **changes):
    return client.post("/api/v1/auth/login", json={"username": "owner", "password": "a sufficiently long test password", **changes}, headers={"X-Requested-With": "EmailAgent", "Origin": "http://localhost:4200"})


def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password("example"), hash_password("example")
    assert first != second
    assert verify_password("example", first)
    assert not verify_password("wrong", first)
    assert not verify_password("example", "malformed")


def test_browser_session_requires_csrf_and_logout_revokes(browser):
    client, _ = browser
    assert client.get("/api/v1/auth/session").status_code == 401
    response = login(client)
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert any("email_session=" in value and "HttpOnly" in value and "Path=/api" in value for value in cookies)
    assert client.get("/api/v1/auth/session").json() == {"username": "owner"}
    token = client.cookies.get("email_session")
    assert client.post("/api/v1/probe").status_code == 403
    assert client.post("/api/v1/probe", headers={"X-XSRF-TOKEN": "wrong"}).status_code == 403
    csrf = client.cookies.get("XSRF-TOKEN")
    assert client.post("/api/v1/probe", headers={"X-XSRF-TOKEN": csrf}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"X-XSRF-TOKEN": csrf}).status_code == 204
    client.cookies.set("email_session", token)
    assert client.get("/api/v1/auth/session").status_code == 401


def test_bad_credentials_and_untrusted_origin_do_not_create_session(browser):
    client, _ = browser
    assert login(client, password="wrong").status_code == 401
    assert login(client, username="unknown").status_code == 401
    response = client.post("/api/v1/auth/login", json={"username":"owner","password":"a sufficiently long test password"}, headers={"X-Requested-With":"EmailAgent","Origin":"https://evil.example"})
    assert response.status_code == 403
    assert not client.cookies.get("email_session")


def test_login_is_throttled(browser):
    client, _ = browser
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 429


def test_expired_session_is_rejected(browser, db):
    client, settings = browser
    assert login(client).status_code == 200
    row = SessionService(db, settings).repository.get(digest(client.cookies.get("email_session")))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/session").status_code == 401


def test_password_rotation_invalidates_sessions(browser, monkeypatch):
    client, settings = browser
    login(client)
    monkeypatch.setattr(settings, "browser_password_hash", hash_password("a different long password"))
    assert client.get("/api/v1/auth/session").status_code == 401


def test_api_key_clients_continue_to_work_without_csrf(browser):
    client, settings = browser
    assert client.post("/api/v1/probe", headers={"X-API-Key": settings.api_key}).status_code == 200
    assert client.post("/api/v1/probe", headers={"X-API-Key": "invalid"}).status_code == 401


def test_production_session_cookies_are_secure(browser, monkeypatch):
    client, settings = browser
    monkeypatch.setattr(settings, "app_env", "production")
    response = login(client)
    assert response.status_code == 200
    assert all("Secure" in value for value in response.headers.get_list("set-cookie"))
