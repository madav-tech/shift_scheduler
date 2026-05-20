from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def _add(client, name: str, role: str, start: str, end: str) -> int:
    create = client.post("/roster", data={"name": name, "role": role}, follow_redirects=False)
    pid = int(create.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/roster/{pid}/periods", data={"start_date": start, "end_date": end})
    return pid


def test_candidates_requires_auth(client) -> None:
    r = client.get("/shift/2026-06-10/morning/candidates?slot=operator&position=0",
                   follow_redirects=False)
    assert r.status_code == 302


def test_candidates_filters_by_role_and_arrival(client, settings) -> None:
    _login(client, settings)
    op_id = _add(client, "מפעיל", "operator", "2026-06-09", "2026-06-15")
    cm_id = _add(client, "מפקד", "commander", "2026-06-09", "2026-06-15")
    _ = _add(client, "ארן", "operator", "2026-06-10", "2026-06-15")  # arrival day morning blocked

    r = client.get("/shift/2026-06-10/morning/candidates?slot=commander&position=0")
    assert r.status_code == 200
    assert "מפקד" in r.text
    assert "מפעיל" not in r.text  # operator can't fill commander slot
    assert "ארן" not in r.text     # arrival day morning blocked

    r = client.get("/shift/2026-06-10/morning/candidates?slot=operator&position=0")
    assert "מפעיל" in r.text
    assert "מפקד" in r.text   # commanders may fill operator slots
    assert "ארן" not in r.text
    assert op_id and cm_id  # silence unused


def test_candidates_typeahead_q(client, settings) -> None:
    _login(client, settings)
    _add(client, "אבי", "operator", "2026-06-01", "2026-06-30")
    _add(client, "בני", "operator", "2026-06-01", "2026-06-30")
    r = client.get("/shift/2026-06-10/noon/candidates?slot=operator&position=0&q=אב")
    assert "אבי" in r.text
    assert "בני" not in r.text
