import pytest

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password
from shift_scheduler.config import Settings, get_settings


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
