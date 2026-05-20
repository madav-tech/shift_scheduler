from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from shift_scheduler.audit import write_log
from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    LoginRateLimiter,
    client_ip,
    sign_session,
    verify_password,
)
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.db import get_db
from shift_scheduler.main import templates

router = APIRouter()
rate_limiter = LoginRateLimiter()


@router.get("/login")
def get_login(request: Request):
    return templates.TemplateResponse(
        request, "login.html", {"title": "התחברות", "error": None}
    )


@router.post("/login")
def post_login(
    request: Request,
    password: str = Form(...),
    settings: Settings = Depends(get_settings),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    ip = client_ip(request)
    if rate_limiter.is_locked(ip):
        write_log(db, "login_failed", {"reason": "rate_limited"}, actor_ip=ip)
        db.commit()
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "התחברות", "error": "החשבון נעול זמנית — נסה שוב מאוחר יותר"},
            status_code=200,
        )

    if not verify_password(settings.admin_password_hash, password):
        rate_limiter.register_failure(ip)
        write_log(db, "login_failed", {"reason": "wrong_password"}, actor_ip=ip)
        db.commit()
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "התחברות", "error": "סיסמה שגויה"},
            status_code=200,
        )

    rate_limiter.register_success(ip)
    token = sign_session(
        "admin",
        secret=settings.session_secret,
        max_age_seconds=settings.session_max_age_seconds,
    )
    write_log(db, "login_success", {"sub": "admin"}, actor_ip=ip)
    db.commit()
    response = RedirectResponse(url="/schedule", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
def post_logout(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
):
    write_log(db, "logout", {}, actor_ip=client_ip(request))
    db.commit()
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
