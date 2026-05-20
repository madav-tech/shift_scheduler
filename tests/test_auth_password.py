from shift_scheduler.auth import hash_password, verify_password


def test_hash_password_returns_argon2_string() -> None:
    h = hash_password("hunter2")
    assert h.startswith("$argon2")


def test_verify_password_accepts_correct() -> None:
    h = hash_password("hunter2")
    assert verify_password(h, "hunter2") is True


def test_verify_password_rejects_wrong() -> None:
    h = hash_password("hunter2")
    assert verify_password(h, "wrong") is False


def test_verify_password_handles_empty_hash() -> None:
    assert verify_password("", "anything") is False
