from datetime import date as date_type, datetime, timedelta, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Jerusalem")


class ShiftKind(StrEnum):
    MORNING = "morning"
    NOON = "noon"
    NIGHT = "night"


_SHIFT_HOURS: dict[ShiftKind, tuple[int, int]] = {
    # (start_hour, day_offset_to_end_date) — wall-clock duration is always 8 hours.
    ShiftKind.MORNING: (6, 0),
    ShiftKind.NOON: (14, 0),
    ShiftKind.NIGHT: (22, 1),
}


def _to_fixed_offset(dt: datetime) -> datetime:
    """Normalize a ZoneInfo-tagged datetime to its fixed UTC offset.

    Python's ``datetime.__sub__`` short-circuits when both operands share the
    *same* ``tzinfo`` object and returns the naive wall-clock delta — which
    silently produces 8 h for shifts that actually span a DST transition.
    Converting each endpoint to a fixed-offset ``timezone(...)`` keeps equality
    against the original ``ZoneInfo`` value (aware-datetime ``==`` compares UTC
    instants) while forcing subtraction down the UTC-difference path.
    """
    return dt.astimezone(timezone(dt.utcoffset() or timedelta(0)))


def shift_window(d: date_type, kind: ShiftKind | str) -> tuple[datetime, datetime]:
    """Return (start_dt, end_dt) for the shift, both timezone-aware in Asia/Jerusalem.

    Wall-clock hours are 06–14 (morning), 14–22 (noon), 22–06 next day (night).
    Around DST transitions the elapsed real time may differ from 8 wall hours;
    each endpoint is normalized to its fixed UTC offset so ``end - start``
    yields true elapsed time rather than a wall-clock subtraction.
    """
    if isinstance(kind, str) and not isinstance(kind, ShiftKind):
        try:
            kind = ShiftKind(kind)
        except ValueError as e:
            raise ValueError(f"Unknown shift kind: {kind!r}") from e

    start_hour, day_offset = _SHIFT_HOURS[kind]
    end_date = d + timedelta(days=day_offset)
    end_hour = (start_hour + 8) % 24
    start_dt = datetime(d.year, d.month, d.day, start_hour, 0, tzinfo=TZ)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, end_hour, 0, tzinfo=TZ)
    return _to_fixed_offset(start_dt), _to_fixed_offset(end_dt)
