from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from shift_scheduler.db import Base, build_engine, build_session_factory
from shift_scheduler.models import Person, PresencePeriod


@pytest.fixture
def session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = build_session_factory(engine)
    with SessionLocal() as s:
        yield s


def test_create_person_defaults(session) -> None:
    p = Person(name="דניאל", role="commander")
    session.add(p)
    session.commit()
    assert p.id is not None
    assert p.archived is False
    assert p.created_at is not None


def test_person_role_check_constraint(session) -> None:
    session.add(Person(name="x", role="bogus"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_presence_period_check_end_ge_start(session) -> None:
    p = Person(name="ענת", role="operator")
    session.add(p)
    session.commit()
    bad = PresencePeriod(person_id=p.id, start_date=date(2026, 6, 5), end_date=date(2026, 6, 1))
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()


def test_presence_period_back_ref(session) -> None:
    p = Person(name="עידו", role="operator")
    session.add(p)
    session.commit()
    pp = PresencePeriod(person_id=p.id, start_date=date(2026, 6, 1), end_date=date(2026, 6, 7))
    session.add(pp)
    session.commit()
    session.refresh(p)
    assert len(p.presence_periods) == 1
    assert p.presence_periods[0].end_date == date(2026, 6, 7)
