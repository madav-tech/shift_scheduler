from datetime import date

from shift_scheduler.shifts import EligibilityResult, ShiftKind, is_eligible


def _person(role: str = "operator", archived: bool = False) -> dict:
    return {"role": role, "archived": archived}


def _period(start, end) -> dict:
    return {"start_date": start, "end_date": end}


def test_archived_person_not_eligible() -> None:
    res = is_eligible(_person(archived=True), [_period(date(2026, 6, 1), date(2026, 6, 30))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.MORNING, slot="operator")
    assert res == EligibilityResult(eligible=False, reason="archived")


def test_no_period_covers_date() -> None:
    res = is_eligible(_person(), [_period(date(2026, 6, 1), date(2026, 6, 5))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.NOON, slot="operator")
    assert res == EligibilityResult(eligible=False, reason="no_period")


def test_arrival_day_morning_blocked() -> None:
    res = is_eligible(_person(), [_period(date(2026, 6, 10), date(2026, 6, 20))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.MORNING, slot="operator")
    assert res == EligibilityResult(eligible=False, reason="arrival_morning")


def test_arrival_day_noon_allowed() -> None:
    res = is_eligible(_person(), [_period(date(2026, 6, 10), date(2026, 6, 20))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.NOON, slot="operator")
    assert res.eligible


def test_last_day_night_allowed() -> None:
    res = is_eligible(_person(), [_period(date(2026, 6, 1), date(2026, 6, 10))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.NIGHT, slot="operator")
    assert res.eligible


def test_operator_cannot_fill_commander_slot() -> None:
    res = is_eligible(_person(role="operator"), [_period(date(2026, 6, 1), date(2026, 6, 30))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.MORNING, slot="commander")
    assert res == EligibilityResult(eligible=False, reason="role_mismatch")


def test_commander_can_fill_operator_slot() -> None:
    res = is_eligible(_person(role="commander"), [_period(date(2026, 6, 1), date(2026, 6, 30))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.NOON, slot="operator")
    assert res.eligible


def test_commander_can_fill_commander_slot() -> None:
    res = is_eligible(_person(role="commander"), [_period(date(2026, 6, 1), date(2026, 6, 30))],
                      shift_date=date(2026, 6, 10), kind=ShiftKind.NOON, slot="commander")
    assert res.eligible
