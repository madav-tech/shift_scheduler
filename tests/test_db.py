from sqlalchemy import text

from shift_scheduler.db import Base, build_engine, build_session_factory


def test_engine_executes_select_one() -> None:
    engine = build_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


def test_session_factory_yields_working_session() -> None:
    engine = build_engine("sqlite:///:memory:")
    SessionLocal = build_session_factory(engine)
    with SessionLocal() as s:
        assert s.execute(text("SELECT 2")).scalar_one() == 2


def test_base_is_declarative_base() -> None:
    assert hasattr(Base, "metadata")
