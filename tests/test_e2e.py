import re

from shift_scheduler.auth import hash_password


def test_full_happy_path(client, settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")

    r = client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert r.status_code == 302

    r = client.post("/roster", data={"name": "טליה", "role": "operator"}, follow_redirects=False)
    assert r.status_code == 302
    pid = int(r.headers["location"].rsplit("/", 1)[-1])

    r = client.post(
        f"/roster/{pid}/periods",
        data={"start_date": "2026-06-01", "end_date": "2026-06-30"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    r = client.post(
        "/shift/2026-06-10/noon/assign",
        data={"slot": "operator", "position": "0", "person_id": str(pid)},
    )
    assert r.status_code == 200

    page = client.get("/schedule?start=2026-06-01&end=2026-06-14")
    assert page.status_code == 200
    assert "טליה" in page.text

    assert "sidebar-person-" in page.text
    assert re.search(r"chip\s+shift", page.text)
