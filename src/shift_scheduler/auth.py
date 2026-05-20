from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

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
