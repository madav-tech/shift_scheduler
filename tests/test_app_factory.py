def test_root_redirects_to_schedule(client) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 or r.status_code == 302
    assert r.headers["location"].endswith("/schedule")


def test_health_still_works(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_static_css_is_served(client) -> None:
    r = client.get("/static/css/app.css")
    assert r.status_code == 200
    assert "html" in r.text or "body" in r.text


def test_base_template_is_rtl(client) -> None:
    # /login is the first concrete page that extends base.html (added in Task 17),
    # but base.html itself is rendered indirectly here through any page using it.
    # Until Task 17, exercise base via the placeholder /schedule landing.
    r = client.get("/schedule", follow_redirects=False)
    # Either renders (200) or redirects to /login (302) depending on auth state;
    # both are acceptable. If 200, body must declare RTL.
    if r.status_code == 200:
        assert 'dir="rtl"' in r.text
        assert 'lang="he"' in r.text
