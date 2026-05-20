import time
from collections import deque
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.exceptions import HTTPException

from shift_scheduler.config import Settings, get_settings

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    if not stored_hash:
        return False
    try:
        return _hasher.verify(stored_hash, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


_SESSION_SALT = "shift-scheduler.session.v1"


class SessionInvalid(Exception):
    pass


class SessionExpired(Exception):
    pass


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret, salt=_SESSION_SALT)


def sign_session(subject: str, *, secret: str, max_age_seconds: int) -> str:
    """Sign a token carrying `subject` (e.g. 'admin'). max_age_seconds is checked at verify time."""
    return _serializer(secret).dumps({"sub": subject})


def verify_session(token: str, *, secret: str, max_age_seconds: int) -> str:
    try:
        payload = _serializer(secret).loads(token, max_age=max_age_seconds)
    except SignatureExpired as e:
        raise SessionExpired(str(e)) from e
    except BadSignature as e:
        raise SessionInvalid(str(e)) from e
    if not isinstance(payload, dict) or "sub" not in payload:
        raise SessionInvalid("malformed payload")
    return str(payload["sub"])


class LoginRateLimiter:
    """Per-IP failed-login tracker with sliding-window lockout. Resets on process restart."""

    def __init__(self, *, max_failures: int = 5, window_seconds: int = 15 * 60,
                 lockout_seconds: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _now(self, now: float | None) -> float:
        return time.monotonic() if now is None else now

    def _purge(self, key: str, now: float) -> None:
        dq = self._failures.get(key)
        if dq is None:
            return
        cutoff = now - max(self.window_seconds, self.lockout_seconds)
        while dq and dq[0] < cutoff:
            dq.popleft()
        if not dq:
            del self._failures[key]

    def register_failure(self, key: str, *, now: float | None = None) -> None:
        t = self._now(now)
        with self._lock:
            self._failures.setdefault(key, deque()).append(t)
            self._purge(key, t)

    def register_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def is_locked(self, key: str, *, now: float | None = None) -> bool:
        t = self._now(now)
        with self._lock:
            self._purge(key, t)
            dq = self._failures.get(key)
            if dq is None:
                return False
            return len(dq) >= self.max_failures


SESSION_COOKIE_NAME = "ss_session"


def client_ip(request: Request) -> str:
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf
    if request.client is None:
        return ""
    return request.client.host


class _RedirectToLogin(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=302, detail="login required")


def _current_subject(request: Request, settings: Settings) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return verify_session(token, secret=settings.session_secret,
                              max_age_seconds=settings.session_max_age_seconds)
    except (SessionInvalid, SessionExpired):
        return None


def require_editor():
    """FastAPI dependency: 302 to /login when not authenticated, otherwise pass through."""

    def _dep(request: Request, settings: Settings = Depends(get_settings)) -> str:  # noqa: B008
        sub = _current_subject(request, settings)
        if sub is None:
            raise _RedirectToLogin()
        return sub

    return Depends(_dep)


def install_auth_exception_handler(app) -> None:
    @app.exception_handler(_RedirectToLogin)
    async def _handle(_request: Request, _exc: _RedirectToLogin):  # type: ignore[no-untyped-def]
        return RedirectResponse(url="/login", status_code=302)
