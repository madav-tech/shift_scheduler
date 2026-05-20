from datetime import date

from shift_scheduler.shifts import (
    RestSeverity,
    ShiftKind,
    build_rest_chain,
    classify_gap_hours,
    projected_worst_gap,
    rest_gap_hours,
    shift_window,
)


def test_classify_gap_hours_critical() -> None:
    assert classify_gap_hours(7.99) == RestSeverity.CRITICAL


def test_classify_gap_hours_warning_exactly_8() -> None:
    assert classify_gap_hours(8.0) == RestSeverity.WARNING


def test_classify_gap_hours_ok() -> None:
    assert classify_gap_hours(8.0001) == RestSeverity.OK
    assert classify_gap_hours(24) == RestSeverity.OK


def test_rest_gap_hours_morning_to_noon_same_day_is_zero() -> None:
    a_start, a_end = shift_window(date(2026, 6, 10), ShiftKind.MORNING)
    b_start, b_end = shift_window(date(2026, 6, 10), ShiftKind.NOON)
    assert rest_gap_hours(a_end, b_start) == 0.0


def test_rest_gap_hours_noon_to_next_day_morning_is_8() -> None:
    _, a_end = shift_window(date(2026, 6, 10), ShiftKind.NOON)
    b_start, _ = shift_window(date(2026, 6, 11), ShiftKind.MORNING)
    assert rest_gap_hours(a_end, b_start) == 8.0


def test_build_rest_chain_orders_and_classifies() -> None:
    s1 = (ShiftKind.MORNING, date(2026, 6, 10))
    s2 = (ShiftKind.NIGHT, date(2026, 6, 10))
    s3 = (ShiftKind.NOON, date(2026, 6, 11))
    chain = build_rest_chain([s2, s1, s3])
    kinds = [item.kind for item in chain.shifts]
    assert kinds == [ShiftKind.MORNING, ShiftKind.NIGHT, ShiftKind.NOON]
    # Morning ends 14:00, Night starts 22:00 → 8h → warning.
    # Night ends 06:00 next day, Noon starts 14:00 → 8h → warning.
    assert [g.severity for g in chain.gaps] == [RestSeverity.WARNING, RestSeverity.WARNING]


def test_projected_worst_gap_uses_neighbours() -> None:
    existing = [
        (ShiftKind.MORNING, date(2026, 6, 9)),  # ends 14:00 day 9
        (ShiftKind.MORNING, date(2026, 6, 11)),  # starts 06:00 day 11
    ]
    # Candidate noon on day 10: prev gap = 14:00 day9 → 14:00 day10 = 24h ok;
    # next gap = 22:00 day10 → 06:00 day11 = 8h warning. Worst = warning.
    sev = projected_worst_gap(
        existing,
        candidate_kind=ShiftKind.NOON,
        candidate_date=date(2026, 6, 10),
    )
    assert sev == RestSeverity.WARNING


def test_projected_worst_gap_no_neighbours_returns_none() -> None:
    sev = projected_worst_gap(
        [],
        candidate_kind=ShiftKind.MORNING,
        candidate_date=date(2026, 6, 10),
    )
    assert sev is None
