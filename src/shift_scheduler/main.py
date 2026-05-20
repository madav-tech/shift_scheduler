from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    SessionExpired,
    SessionInvalid,
    install_auth_exception_handler,
    verify_session,
)
from shift_scheduler.config import get_settings
from shift_scheduler.db import init_db

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


def _current_user_processor(request: Request) -> dict[str, str | None]:
    settings = get_settings()
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return {"current_user": None}
    try:
        sub = verify_session(
            token,
            secret=settings.session_secret,
            max_age_seconds=settings.session_max_age_seconds,
        )
        return {"current_user": sub}
    except (SessionInvalid, SessionExpired):
        return {"current_user": None}


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
    context_processors=[_current_user_processor],
)


def build_app() -> FastAPI:
    settings = get_settings()
    init_db(settings.database_url)

    app = FastAPI(title="Shift Scheduler")
    install_auth_exception_handler(app)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/schedule", status_code=302)

    @app.get("/schedule")
    def schedule_placeholder(request: Request):
        # Replaced in Task 22 with the real handler.
        return templates.TemplateResponse(request, "base.html",
                                          {"title": "לוח זמנים", "content": ""})

    return app


app = build_app()
