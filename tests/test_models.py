from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from shift_scheduler.db import Base, build_engine, build_session_factory
from shift_scheduler.models import EditLog, Person, PresencePeriod, Shift, ShiftAssignment


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


def test_shift_unique_date_kind(session) -> None:
    session.add(Shift(date=date(2026, 6, 1), kind="morning"))
    session.add(Shift(date=date(2026, 6, 1), kind="morning"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_shift_assignment_unique_slot_position(session) -> None:
    p1 = Person(name="A", role="commander")
    p2 = Person(name="B", role="commander")
    s = Shift(date=date(2026, 6, 1), kind="morning")
    session.add_all([p1, p2, s])
    session.commit()
    session.add(ShiftAssignment(shift_id=s.id, person_id=p1.id, slot="commander", position=0))
    session.commit()
    session.add(ShiftAssignment(shift_id=s.id, person_id=p2.id, slot="commander", position=0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_shift_assignment_unique_person_per_shift(session) -> None:
    p = Person(name="C", role="operator")
    s = Shift(date=date(2026, 6, 2), kind="noon")
    session.add_all([p, s])
    session.commit()
    session.add(ShiftAssignment(shift_id=s.id, person_id=p.id, slot="operator", position=0))
    session.commit()
    session.add(ShiftAssignment(shift_id=s.id, person_id=p.id, slot="operator", position=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_edit_log_create(session) -> None:
    e = EditLog(ip="1.2.3.4", action="assign", entity_type="shift_assignment", entity_id=1, payload_json='{"a":1}')
    session.add(e)
    session.commit()
    assert e.id is not None
    assert e.ts is not None
