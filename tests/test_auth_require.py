from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    client_ip,
    install_auth_exception_handler,
    require_editor,
    sign_session,
)
from shift_scheduler.config import Settings


def _build_app(settings: Settings) -> FastAPI:
    app = FastAPI()

    from shift_scheduler.config import get_settings

    app.dependency_overrides[get_settings] = lambda: settings
    install_auth_exception_handler(app)

    @app.get("/secret")
    def secret(_=require_editor()) -> PlainTextResponse:  # noqa: B008
        return PlainTextResponse("ok")

    @app.get("/whoami")
    def whoami(request: Request) -> PlainTextResponse:
        return PlainTextResponse(client_ip(request))

    return app


def test_require_editor_redirects_without_cookie() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    client = TestClient(app, follow_redirects=False)
    r = client.get("/secret")
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login")


def test_require_editor_allows_with_valid_cookie() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    token = sign_session(
        "admin", secret=settings.session_secret, max_age_seconds=settings.session_max_age_seconds
    )
    client = TestClient(app, cookies={SESSION_COOKIE_NAME: token})
    r = client.get("/secret")
    assert r.status_code == 200
    assert r.text == "ok"


def test_client_ip_prefers_cf_connecting_ip() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    client = TestClient(app)
    r = client.get("/whoami", headers={"CF-Connecting-IP": "9.9.9.9"})
    assert r.text == "9.9.9.9"


def test_client_ip_falls_back_to_remote_addr() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    client = TestClient(app)
    r = client.get("/whoami")
    assert r.text  # non-empty (TestClient supplies "testclient")
