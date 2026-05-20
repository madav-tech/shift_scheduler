from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from shift_scheduler import db as db_module
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.db import Base, build_engine, build_session_factory


@pytest.fixture
def settings() -> Settings:
    return Settings(
        admin_password_hash="",  # set per-test if needed
        session_secret="test-secret",
        database_url="sqlite:///:memory:",
        cookie_secure=False,
        session_max_age_seconds=3600,
    )


@pytest.fixture
def engine_and_session(settings: Settings):
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = build_session_factory(engine)
    try:
        yield engine, SessionLocal
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(settings: Settings, engine_and_session) -> Iterator[TestClient]:
    from shift_scheduler.main import build_app

    _, SessionLocal = engine_and_session

    def _override_get_db():
        with SessionLocal() as s:
            yield s

    app = build_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[db_module.get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
