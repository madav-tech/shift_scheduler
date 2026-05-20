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


def test_person_detail_shows_name(client, settings) -> None:
    _login(client, settings)
    create = client.post(
        "/roster",
        data={"name": "דן", "role": "operator"},
        follow_redirects=False,
    )
    pid = create.headers["location"].rsplit("/", 1)[-1]
    r = client.get(f"/roster/{pid}")
    assert r.status_code == 200
    assert "דן" in r.text


def test_person_update_changes_name_and_role(client, settings) -> None:
    _login(client, settings)
    create = client.post(
        "/roster",
        data={"name": "דן", "role": "operator"},
        follow_redirects=False,
    )
    pid = create.headers["location"].rsplit("/", 1)[-1]
    r = client.post(
        f"/roster/{pid}",
        data={"name": "דניאל", "role": "commander"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    after = client.get(f"/roster/{pid}")
    assert "דניאל" in after.text
    assert 'value="commander" selected' in after.text


def test_person_archive_hides_from_index(client, settings) -> None:
    _login(client, settings)
    create = client.post(
        "/roster",
        data={"name": "ליאור", "role": "operator"},
        follow_redirects=False,
    )
    pid = create.headers["location"].rsplit("/", 1)[-1]
    r = client.post(f"/roster/{pid}/archive", follow_redirects=False)
    assert r.status_code == 302
    listing = client.get("/roster")
    assert "ליאור" not in listing.text


def test_person_detail_404_when_missing(client, settings) -> None:
    _login(client, settings)
    r = client.get("/roster/9999")
    assert r.status_code == 404


def _create_person(client, settings, name="דן", role="operator") -> int:
    _login(client, settings)
    r = client.post(
        "/roster", data={"name": name, "role": role}, follow_redirects=False
    )
    return int(r.headers["location"].rsplit("/", 1)[-1])


def test_create_period_persists(client, settings) -> None:
    pid = _create_person(client, settings)
    r = client.post(
        f"/roster/{pid}/periods",
        data={"start_date": "2026-06-01", "end_date": "2026-06-10", "note": "תורנות"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    detail = client.get(f"/roster/{pid}")
    assert "2026-06-01" in detail.text
    assert "2026-06-10" in detail.text
    assert "תורנות" in detail.text


def test_create_period_rejects_inverted_dates(client, settings) -> None:
    pid = _create_person(client, settings)
    r = client.post(
        f"/roster/{pid}/periods",
        data={"start_date": "2026-06-10", "end_date": "2026-06-01"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_update_period_changes_dates(client, settings) -> None:
    pid = _create_person(client, settings)
    client.post(
        f"/roster/{pid}/periods",
        data={"start_date": "2026-06-01", "end_date": "2026-06-05"},
    )
    detail = client.get(f"/roster/{pid}")
    import re
    m = re.search(rf"/roster/{pid}/periods/(\d+)/delete", detail.text)
    assert m
    period_id = int(m.group(1))
    r = client.post(
        f"/roster/{pid}/periods/{period_id}",
        data={"start_date": "2026-06-02", "end_date": "2026-06-09", "note": "עודכן"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    after = client.get(f"/roster/{pid}")
    assert "2026-06-09" in after.text


def test_delete_period_removes_it(client, settings) -> None:
    pid = _create_person(client, settings)
    client.post(
        f"/roster/{pid}/periods",
        data={"start_date": "2026-06-01", "end_date": "2026-06-05"},
    )
    detail = client.get(f"/roster/{pid}")
    import re
    period_id = int(
        re.search(rf"/roster/{pid}/periods/(\d+)/delete", detail.text).group(1)
    )
    r = client.post(
        f"/roster/{pid}/periods/{period_id}/delete", follow_redirects=False
    )
    assert r.status_code == 302
    after = client.get(f"/roster/{pid}")
    assert "2026-06-01" not in after.text
