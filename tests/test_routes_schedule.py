from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session(
        "admin",
        secret=settings.session_secret,
        max_age_seconds=settings.session_max_age_seconds,
    )
    client.cookies.set(SESSION_COOKIE_NAME, token)


def test_get_schedule_default_renders_14_days(client) -> None:
    r = client.get("/schedule")
    assert r.status_code == 200
    assert 'dir="rtl"' in r.text
    assert "morning" in r.text.lower() or "בוקר" in r.text


def test_get_schedule_with_explicit_range(client) -> None:
    r = client.get("/schedule?start=2026-06-01&end=2026-06-14")
    assert r.status_code == 200
    assert "2026-06-01" in r.text
    assert "2026-06-14" in r.text


def test_invalid_date_param_400(client) -> None:
    r = client.get("/schedule?start=not-a-date")
    assert r.status_code == 400


def test_inverted_range_400(client) -> None:
    r = client.get("/schedule?start=2026-06-10&end=2026-06-01")
    assert r.status_code == 400


def test_schedule_shows_logged_in_actions(client, settings) -> None:
    _login(client, settings)
    r = client.get("/schedule")
    assert "התנתק" in r.text
