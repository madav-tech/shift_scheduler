from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
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


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    eligible: bool
    reason: str | None = None


def _has_covering_period(
    periods: Sequence[Mapping[str, Any]], d: date_type
) -> Mapping[str, Any] | None:
    for p in periods:
        if p["start_date"] <= d <= p["end_date"]:
            return p
    return None


def is_eligible(
    person: Mapping[str, Any],
    periods: Sequence[Mapping[str, Any]],
    *,
    shift_date: date_type,
    kind: ShiftKind | str,
    slot: str,
) -> EligibilityResult:
    """Pure-data eligibility check. `person` and `periods` are dict-like.

    `person` keys: role, archived. `periods` items: start_date, end_date.
    """
    if isinstance(kind, str) and not isinstance(kind, ShiftKind):
        kind = ShiftKind(kind)

    if person.get("archived"):
        return EligibilityResult(False, "archived")

    if slot == "commander" and person.get("role") != "commander":
        return EligibilityResult(False, "role_mismatch")

    covering = _has_covering_period(periods, shift_date)
    if covering is None:
        return EligibilityResult(False, "no_period")

    if kind == ShiftKind.MORNING and covering["start_date"] == shift_date:
        return EligibilityResult(False, "arrival_morning")

    return EligibilityResult(True, None)


class RestSeverity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    OK = "ok"


def classify_gap_hours(hours: float) -> RestSeverity:
    if hours < 8:
        return RestSeverity.CRITICAL
    if hours == 8:
        return RestSeverity.WARNING
    return RestSeverity.OK


def rest_gap_hours(prev_end: datetime, next_start: datetime) -> float:
    return (next_start - prev_end).total_seconds() / 3600.0


@dataclass(frozen=True, slots=True)
class ChainShift:
    kind: ShiftKind
    date: date_type
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class ChainGap:
    hours: float
    severity: RestSeverity


@dataclass(frozen=True, slots=True)
class RestChain:
    shifts: list[ChainShift]
    gaps: list[ChainGap]


def build_rest_chain(items: Sequence[tuple[ShiftKind, date_type]]) -> RestChain:
    """Given (kind, date) pairs, build a sorted chain plus the gaps between them."""
    expanded: list[ChainShift] = []
    for kind, d in items:
        start, end = shift_window(d, kind)
        expanded.append(ChainShift(kind=kind, date=d, start=start, end=end))
    expanded.sort(key=lambda s: s.start)

    gaps: list[ChainGap] = []
    for prev, nxt in zip(expanded, expanded[1:], strict=False):
        h = rest_gap_hours(prev.end, nxt.start)
        gaps.append(ChainGap(hours=h, severity=classify_gap_hours(h)))
    return RestChain(shifts=expanded, gaps=gaps)


def projected_worst_gap(
    existing: Sequence[tuple[ShiftKind, date_type]],
    *,
    candidate_kind: ShiftKind,
    candidate_date: date_type,
) -> RestSeverity | None:
    """Compute worst severity of (prev→candidate) and (candidate→next) gaps.

    Returns ``None`` if the candidate has no neighbouring shifts in ``existing``.
    """
    cand_start, cand_end = shift_window(candidate_date, candidate_kind)
    prev_end: datetime | None = None
    next_start: datetime | None = None
    for kind, d in existing:
        s, e = shift_window(d, kind)
        if e <= cand_start and (prev_end is None or e > prev_end):
            prev_end = e
        if s >= cand_end and (next_start is None or s < next_start):
            next_start = s

    severities: list[RestSeverity] = []
    if prev_end is not None:
        severities.append(classify_gap_hours(rest_gap_hours(prev_end, cand_start)))
    if next_start is not None:
        severities.append(classify_gap_hours(rest_gap_hours(cand_end, next_start)))
    if not severities:
        return None

    order = {RestSeverity.CRITICAL: 0, RestSeverity.WARNING: 1, RestSeverity.OK: 2}
    return min(severities, key=lambda s: order[s])
