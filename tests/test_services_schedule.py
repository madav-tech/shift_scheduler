from datetime import date

import pytest

from shift_scheduler.db import Base, build_engine, build_session_factory
from shift_scheduler.models import Person, PresencePeriod, Shift, ShiftAssignment
from shift_scheduler.services import build_schedule_view
from shift_scheduler.shifts import RestSeverity, ShiftKind


@pytest.fixture
def session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = build_session_factory(engine)
    with SessionLocal() as s:
        yield s


def test_empty_schedule_returns_14_days(session) -> None:
    view = build_schedule_view(session, start=date(2026, 6, 1), end=date(2026, 6, 14))
    assert len(view.days) == 14
    assert view.days[0].date == date(2026, 6, 1)
    assert view.days[-1].date == date(2026, 6, 14)
    for day in view.days:
        assert set(day.cells.keys()) == {"morning", "noon", "night"}
        for cell in day.cells.values():
            assert cell.assigned == []
            assert cell.worst_severity is None


def test_cell_tint_warning_on_8h_chain(session) -> None:
    p = Person(name="A", role="commander")
    s_noon = Shift(date=date(2026, 6, 1), kind="noon")
    s_morn = Shift(date=date(2026, 6, 2), kind="morning")
    session.add_all([p, s_noon, s_morn])
    session.commit()
    session.add_all(
        [
            ShiftAssignment(shift_id=s_noon.id, person_id=p.id, slot="commander", position=0),
            ShiftAssignment(shift_id=s_morn.id, person_id=p.id, slot="commander", position=0),
        ]
    )
    session.add(
        PresencePeriod(person_id=p.id, start_date=date(2026, 5, 1), end_date=date(2026, 6, 30))
    )
    session.commit()

    view = build_schedule_view(session, start=date(2026, 6, 1), end=date(2026, 6, 14))
    noon_cell = view.days[0].cells["noon"]
    morn_cell = view.days[1].cells["morning"]
    assert noon_cell.worst_severity == RestSeverity.WARNING
    assert morn_cell.worst_severity == RestSeverity.WARNING


def test_sidebar_lists_only_overlapping_non_archived(session) -> None:
    p_in = Person(name="In", role="operator")
    p_out = Person(name="Out", role="operator")
    p_arch = Person(name="Arch", role="operator", archived=True)
    session.add_all([p_in, p_out, p_arch])
    session.commit()
    session.add_all(
        [
            PresencePeriod(
                person_id=p_in.id, start_date=date(2026, 6, 5), end_date=date(2026, 6, 8)
            ),
            PresencePeriod(
                person_id=p_out.id, start_date=date(2026, 7, 1), end_date=date(2026, 7, 3)
            ),
            PresencePeriod(
                person_id=p_arch.id, start_date=date(2026, 6, 5), end_date=date(2026, 6, 8)
            ),
        ]
    )
    session.commit()

    view = build_schedule_view(session, start=date(2026, 6, 1), end=date(2026, 6, 14))
    names = [row.person.name for row in view.sidebar_rows]
    assert "In" in names
    assert "Out" not in names
    assert "Arch" not in names


def test_cell_capacity_matches_shift_kind(session) -> None:
    view = build_schedule_view(session, start=date(2026, 6, 1), end=date(2026, 6, 1))
    cells = view.days[0].cells
    assert cells["morning"].capacity == {"commander": 1, "operator": 2}
    assert cells["noon"].capacity == {"commander": 1, "operator": 2}
    assert cells["night"].capacity == {"commander": 1, "operator": 1}
    for cell in cells.values():
        assert isinstance(cell.kind, ShiftKind)
