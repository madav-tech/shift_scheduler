import time

import pytest

from shift_scheduler.auth import SessionExpired, SessionInvalid, sign_session, verify_session


def test_sign_and_verify_roundtrip() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=60)
    assert verify_session(token, secret="s3cret", max_age_seconds=60) == "admin"


def test_verify_rejects_tampered_token() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=60)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    with pytest.raises(SessionInvalid):
        verify_session(tampered, secret="s3cret", max_age_seconds=60)


def test_verify_rejects_wrong_secret() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=60)
    with pytest.raises(SessionInvalid):
        verify_session(token, secret="other", max_age_seconds=60)


def test_verify_rejects_expired() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=1)
    time.sleep(2.1)
    with pytest.raises(SessionExpired):
        verify_session(token, secret="s3cret", max_age_seconds=1)
