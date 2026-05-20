from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from shift_scheduler.shifts import ShiftKind, shift_window

TZ = ZoneInfo("Asia/Jerusalem")


def test_morning_window() -> None:
    start, end = shift_window(date(2026, 6, 10), ShiftKind.MORNING)
    assert start == datetime(2026, 6, 10, 6, 0, tzinfo=TZ)
    assert end == datetime(2026, 6, 10, 14, 0, tzinfo=TZ)


def test_noon_window() -> None:
    start, end = shift_window(date(2026, 6, 10), ShiftKind.NOON)
    assert start == datetime(2026, 6, 10, 14, 0, tzinfo=TZ)
    assert end == datetime(2026, 6, 10, 22, 0, tzinfo=TZ)


def test_night_window_crosses_midnight() -> None:
    start, end = shift_window(date(2026, 6, 10), ShiftKind.NIGHT)
    assert start == datetime(2026, 6, 10, 22, 0, tzinfo=TZ)
    assert end == datetime(2026, 6, 11, 6, 0, tzinfo=TZ)


def test_dst_spring_forward_night_2026_03_26() -> None:
    # IDT begins Friday 2026-03-27 at 02:00 IST → 03:00 IDT. The night that
    # actually spans the spring-forward is the night of 2026-03-26 (Thursday
    # 22:00 IST → Friday 06:00 IDT). Elapsed real time is 7 hours, not 8.
    start, end = shift_window(date(2026, 3, 26), ShiftKind.NIGHT)
    assert (end - start).total_seconds() == 7 * 3600


def test_dst_fall_back_night_2026_10_24() -> None:
    # IST returns Sunday 2026-10-25 at 02:00 → 01:00. Friday/Saturday night
    # is the night before; pick 2026-10-24 night which spans the fall-back.
    start, end = shift_window(date(2026, 10, 24), ShiftKind.NIGHT)
    assert (end - start).total_seconds() == 9 * 3600


def test_invalid_kind_raises() -> None:
    with pytest.raises(ValueError):
        shift_window(date(2026, 6, 10), "tea-break")  # type: ignore[arg-type]
