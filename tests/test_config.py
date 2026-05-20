from shift_scheduler.config import Settings


def test_settings_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$argon2id$abc")
    monkeypatch.setenv("SESSION_SECRET", "super-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    s = Settings()
    assert s.admin_password_hash == "$argon2id$abc"
    assert s.session_secret == "super-secret"
    assert s.database_url == "sqlite:///./test.db"
    assert s.cookie_secure is False
    assert s.session_max_age_seconds == 12 * 60 * 60
    assert s.timezone == "Asia/Jerusalem"
