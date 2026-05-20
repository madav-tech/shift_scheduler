from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def _add(client, name: str, role: str, start="2026-06-01", end="2026-06-30") -> int:
    r = client.post("/roster", data={"name": name, "role": role}, follow_redirects=False)
    pid = int(r.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/roster/{pid}/periods", data={"start_date": start, "end_date": end})
    return pid


def test_assign_requires_auth(client) -> None:
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "0", "person_id": "1"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login")


def test_assign_writes_row_and_returns_cell_html(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "0", "person_id": str(pid)})
    assert r.status_code == 200
    assert "id=\"cell-2026-06-10-noon\"" in r.text
    assert "דנה" in r.text
    assert "hx-swap-oob" in r.text  # OOB sidebar fragment


def test_assign_rejects_role_mismatch(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    r = client.post("/shift/2026-06-10/morning/assign",
                    data={"slot": "commander", "position": "0", "person_id": str(pid)})
    assert r.status_code == 400


def test_assign_rejects_arrival_morning(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "ארן", "operator", start="2026-06-10", end="2026-06-15")
    r = client.post("/shift/2026-06-10/morning/assign",
                    data={"slot": "operator", "position": "0", "person_id": str(pid)})
    assert r.status_code == 400


def test_assign_rejects_double_booking_same_shift(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    client.post("/shift/2026-06-10/noon/assign",
                data={"slot": "operator", "position": "0", "person_id": str(pid)})
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "1", "person_id": str(pid)})
    assert r.status_code == 400


def test_unassign_removes_row_and_returns_cell(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    client.post("/shift/2026-06-10/noon/assign",
                data={"slot": "operator", "position": "0", "person_id": str(pid)})
    r = client.post("/shift/2026-06-10/noon/unassign",
                    data={"slot": "operator", "position": "0"})
    assert r.status_code == 200
    assert "id=\"cell-2026-06-10-noon\"" in r.text
    assert "דנה" not in r.text
    assert "hx-swap-oob" in r.text


def test_unassign_idempotent_when_empty(client, settings) -> None:
    _login(client, settings)
    r = client.post("/shift/2026-06-10/noon/unassign",
                    data={"slot": "operator", "position": "0"})
    assert r.status_code == 200
    assert "id=\"cell-2026-06-10-noon\"" in r.text


def test_unassign_requires_auth(client) -> None:
    r = client.post("/shift/2026-06-10/noon/unassign",
                    data={"slot": "operator", "position": "0"},
                    follow_redirects=False)
    assert r.status_code == 302
