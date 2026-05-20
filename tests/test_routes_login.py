import json

import pytest
from sqlalchemy import select

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.models import EditLog


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    from shift_scheduler.routes.auth import rate_limiter

    rate_limiter._failures.clear()
    yield
    rate_limiter._failures.clear()


@pytest.fixture
def authed_settings(settings: Settings) -> Settings:
    settings.admin_password_hash = hash_password("hunter2")
    return settings


def test_get_login_renders_form(client) -> None:
    r = client.get("/login")
    assert r.status_code == 200
    assert "סיסמה" in r.text
    assert "name=\"password\"" in r.text


def test_post_login_wrong_password_shows_error(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    r = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert r.status_code == 200
    assert "סיסמה שגויה" in r.text
    assert SESSION_COOKIE_NAME not in r.cookies


def test_post_login_correct_password_sets_cookie_and_redirects(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    r = client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/schedule"
    assert SESSION_COOKIE_NAME in r.cookies


def test_post_logout_clears_cookie_and_redirects(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    client.post("/login", data={"password": "hunter2"})
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"
    assert r.cookies.get(SESSION_COOKIE_NAME) in (None, "")


def test_rate_limiter_locks_after_5_failures(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    for _ in range(5):
        client.post("/login", data={"password": "wrong"})
    r = client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert r.status_code == 200
    assert "נעול" in r.text or "נסה שוב מאוחר" in r.text


def _actions(engine_and_session) -> list[str]:
    _, SessionLocal = engine_and_session
    with SessionLocal() as s:
        return [r.action for r in s.execute(select(EditLog).order_by(EditLog.id)).scalars().all()]


def test_login_success_writes_audit(client, authed_settings, engine_and_session) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert _actions(engine_and_session) == ["login_success"]


def test_login_failed_writes_audit(client, authed_settings, engine_and_session) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    actions = _actions(engine_and_session)
    assert actions == ["login_failed"]

    _, SessionLocal = engine_and_session
    with SessionLocal() as s:
        row = s.execute(select(EditLog)).scalar_one()
        assert json.loads(row.payload_json)["reason"] == "wrong_password"


def test_logout_writes_audit(client, authed_settings, engine_and_session) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    client.post("/login", data={"password": "hunter2"})
    client.post("/logout", follow_redirects=False)
    assert _actions(engine_and_session) == ["login_success", "logout"]
