from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from shift_scheduler.models import Person, PresencePeriod, Shift, ShiftAssignment
from shift_scheduler.shifts import (
    ChainGap,
    ChainShift,
    RestSeverity,
    ShiftKind,
    build_rest_chain,
    classify_gap_hours,
    rest_gap_hours,
    shift_window,
)

_SHIFT_ORDER: list[ShiftKind] = [ShiftKind.MORNING, ShiftKind.NOON, ShiftKind.NIGHT]
_SEVERITY_RANK = {RestSeverity.CRITICAL: 0, RestSeverity.WARNING: 1, RestSeverity.OK: 2}


@dataclass
class CellPerson:
    person_id: int
    name: str
    role: str
    slot: str
    position: int
    severity: RestSeverity | None


@dataclass
class CellView:
    date: date
    kind: ShiftKind
    capacity: dict[str, int]
    assigned: list[CellPerson] = field(default_factory=list)
    worst_severity: RestSeverity | None = None


@dataclass
class DayView:
    date: date
    cells: dict[str, CellView]


@dataclass
class SidebarChain:
    person: Person
    items: list[ChainShift | ChainGap]


@dataclass
class ScheduleView:
    start: date
    end: date
    days: list[DayView]
    sidebar_rows: list[SidebarChain]


def cell_capacity(kind: ShiftKind) -> dict[str, int]:
    if kind == ShiftKind.NIGHT:
        return {"commander": 1, "operator": 1}
    return {"commander": 1, "operator": 2}


def _person_assignments_in_range(
    db: Session, person_id: int, start: date, end: date
) -> list[tuple[ShiftKind, date]]:
    rows = db.execute(
        select(Shift.kind, Shift.date)
        .join(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
        .where(ShiftAssignment.person_id == person_id)
        .where(Shift.date >= start)
        .where(Shift.date <= end)
        .order_by(Shift.date, Shift.kind)
    ).all()
    return [(ShiftKind(k), d) for k, d in rows]


def _worst_severity_for_person_at(
    db: Session, person_id: int, kind: ShiftKind, d: date
) -> RestSeverity | None:
    cand_start, cand_end = shift_window(d, kind)
    nearby = _person_assignments_in_range(
        db, person_id, d - timedelta(days=2), d + timedelta(days=2)
    )
    severities: list[RestSeverity] = []
    prev_end = None
    next_start = None
    for k, dd in nearby:
        s, e = shift_window(dd, k)
        if k == kind and dd == d:
            continue
        if e <= cand_start and (prev_end is None or e > prev_end):
            prev_end = e
        if s >= cand_end and (next_start is None or s < next_start):
            next_start = s
    if prev_end is not None:
        severities.append(classify_gap_hours(rest_gap_hours(prev_end, cand_start)))
    if next_start is not None:
        severities.append(classify_gap_hours(rest_gap_hours(cand_end, next_start)))
    if not severities:
        return None
    return min(severities, key=lambda s: _SEVERITY_RANK[s])


def build_schedule_view(db: Session, *, start: date, end: date) -> ScheduleView:
    assert end >= start
    shifts = (
        db.execute(
            select(Shift)
            .where(Shift.date >= start)
            .where(Shift.date <= end)
            .options(joinedload(Shift.assignments).joinedload(ShiftAssignment.person))
        )
        .unique()
        .scalars()
        .all()
    )

    by_key: dict[tuple[date, str], Shift] = {(s.date, s.kind): s for s in shifts}

    days: list[DayView] = []
    for offset in range((end - start).days + 1):
        d = start + timedelta(days=offset)
        cells: dict[str, CellView] = {}
        for kind in _SHIFT_ORDER:
            cell = CellView(date=d, kind=kind, capacity=cell_capacity(kind))
            shift = by_key.get((d, kind.value))
            if shift is not None:
                worst: RestSeverity | None = None
                for a in shift.assignments:
                    sev = _worst_severity_for_person_at(db, a.person_id, kind, d)
                    cell.assigned.append(
                        CellPerson(
                            person_id=a.person_id,
                            name=a.person.name,
                            role=a.person.role,
                            slot=a.slot,
                            position=a.position,
                            severity=sev,
                        )
                    )
                    if sev is not None and (
                        worst is None or _SEVERITY_RANK[sev] < _SEVERITY_RANK[worst]
                    ):
                        worst = sev
                cell.worst_severity = worst
            cells[kind.value] = cell
        days.append(DayView(date=d, cells=cells))

    overlap_clause = and_(
        PresencePeriod.start_date <= end,
        PresencePeriod.end_date >= start,
    )
    rows = (
        db.execute(
            select(Person)
            .join(PresencePeriod, PresencePeriod.person_id == Person.id)
            .where(Person.archived.is_(False))
            .where(overlap_clause)
            .order_by(Person.name)
            .distinct()
        )
        .scalars()
        .all()
    )

    sidebar_rows: list[SidebarChain] = []
    for p in rows:
        assignments = _person_assignments_in_range(
            db, p.id, start - timedelta(days=1), end + timedelta(days=1)
        )
        chain = build_rest_chain(assignments)
        items: list[ChainShift | ChainGap] = []
        for i, shift in enumerate(chain.shifts):
            items.append(shift)
            if i < len(chain.gaps):
                items.append(chain.gaps[i])
        sidebar_rows.append(SidebarChain(person=p, items=items))

    return ScheduleView(start=start, end=end, days=days, sidebar_rows=sidebar_rows)
