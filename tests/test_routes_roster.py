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


def test_roster_index_public_read(client) -> None:
    r = client.get("/roster")
    assert r.status_code == 200
    assert "סגל" in r.text


def test_roster_create_requires_auth(client) -> None:
    r = client.post(
        "/roster",
        data={"name": "דן", "role": "operator"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login")


def test_roster_create_persists_person(client, settings) -> None:
    _login(client, settings)
    r = client.post(
        "/roster",
        data={"name": "דן", "role": "operator"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].startswith("/roster/")
    listing = client.get("/roster")
    assert "דן" in listing.text


def test_roster_create_rejects_invalid_role(client, settings) -> None:
    _login(client, settings)
    r = client.post("/roster", data={"name": "דן", "role": "wizard"})
    assert r.status_code == 400
    assert "תפקיד" in r.text
