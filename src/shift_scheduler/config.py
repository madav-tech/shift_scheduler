from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    admin_password_hash: str = ""
    session_secret: str = "dev-only-change-me"
    database_url: str = "sqlite:///./data.db"
    cookie_secure: bool = True
    session_max_age_seconds: int = 12 * 60 * 60
    timezone: str = "Asia/Jerusalem"


@lru_cache
def get_settings() -> Settings:
    return Settings()
