import json

import pytest
from sqlalchemy import select

from shift_scheduler.db import Base, build_engine, build_session_factory
from shift_scheduler.models import EditLog


@pytest.fixture
def session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = build_session_factory(engine)
    with SessionLocal() as s:
        yield s


def test_write_log_inserts_row(session) -> None:
    from shift_scheduler.audit import write_log

    write_log(session, "assign", {"shift_date": "2026-06-10", "kind": "noon"}, actor_ip="9.9.9.9")
    session.commit()

    rows = session.execute(select(EditLog)).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "assign"
    assert row.ip == "9.9.9.9"
    assert row.ts is not None
    assert json.loads(row.payload_json) == {"shift_date": "2026-06-10", "kind": "noon"}


def test_write_log_serializes_payload_as_json(session) -> None:
    from shift_scheduler.audit import write_log

    payload = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
    write_log(session, "person_update", payload, actor_ip="1.2.3.4")
    session.commit()

    row = session.execute(select(EditLog)).scalar_one()
    assert json.loads(row.payload_json) == payload


def test_write_log_accepts_empty_actor_ip(session) -> None:
    from shift_scheduler.audit import write_log

    write_log(session, "logout", {}, actor_ip="")
    session.commit()

    row = session.execute(select(EditLog)).scalar_one()
    assert row.action == "logout"
    assert row.ip == ""
    assert json.loads(row.payload_json) == {}


def test_write_log_returns_editlog_row(session) -> None:
    from shift_scheduler.audit import write_log

    row = write_log(session, "login_success", {"sub": "admin"}, actor_ip="10.0.0.1")
    session.commit()

    assert isinstance(row, EditLog)
    assert row.id is not None
    assert row.action == "login_success"


def test_write_log_does_not_commit(session) -> None:
    """write_log should flush but leave commit to the caller."""
    from shift_scheduler.audit import write_log

    write_log(session, "assign", {"x": 1}, actor_ip="1.1.1.1")
    session.rollback()

    rows = session.execute(select(EditLog)).scalars().all()
    assert rows == []
