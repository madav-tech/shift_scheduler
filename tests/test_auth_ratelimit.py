from shift_scheduler.auth import LoginRateLimiter


def test_first_failures_are_allowed() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    assert rl.is_locked("1.1.1.1", now=0.0) is False
    for i in range(4):
        rl.register_failure("1.1.1.1", now=float(i))
    assert rl.is_locked("1.1.1.1", now=4.0) is False


def test_fifth_failure_locks_out() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for i in range(5):
        rl.register_failure("1.1.1.1", now=float(i))
    assert rl.is_locked("1.1.1.1", now=5.0) is True


def test_lockout_clears_after_window() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for i in range(5):
        rl.register_failure("1.1.1.1", now=float(i))
    assert rl.is_locked("1.1.1.1", now=905.0) is False


def test_success_clears_history() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for i in range(4):
        rl.register_failure("1.1.1.1", now=float(i))
    rl.register_success("1.1.1.1")
    for i in range(4):
        rl.register_failure("1.1.1.1", now=10.0 + i)
    assert rl.is_locked("1.1.1.1", now=20.0) is False
