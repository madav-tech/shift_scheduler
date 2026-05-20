from datetime import date as date_type
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    SessionExpired,
    SessionInvalid,
    require_editor,
    verify_session,
)
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.db import get_db
from shift_scheduler.main import templates
from shift_scheduler.models import Person, Shift, ShiftAssignment
from shift_scheduler.services import _person_assignments_in_range, build_schedule_view
from shift_scheduler.shifts import (
    TZ,
    EligibilityResult,
    ShiftKind,
    is_eligible,
    projected_worst_gap,
)

router = APIRouter()

DEFAULT_SPAN_DAYS = 14


def _parse_date(s: str) -> date_type:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"תאריך לא חוקי: {s}") from e


def _today_local() -> date_type:
    return datetime.now(TZ).date()


def _is_logged_in(request: Request, settings: Settings) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    try:
        verify_session(
            token,
            secret=settings.session_secret,
            max_age_seconds=settings.session_max_age_seconds,
        )
        return True
    except (SessionInvalid, SessionExpired):
        return False


@router.get("/schedule", response_class=HTMLResponse)
def schedule_page(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    s_date = _parse_date(start) if start else _today_local()
    e_date = _parse_date(end) if end else (s_date + timedelta(days=DEFAULT_SPAN_DAYS - 1))
    if e_date < s_date:
        raise HTTPException(status_code=400, detail="טווח לא תקין")

    view = build_schedule_view(db, start=s_date, end=e_date)
    span = (e_date - s_date).days + 1
    prev_start = s_date - timedelta(days=span)
    prev_end = s_date - timedelta(days=1)
    next_start = e_date + timedelta(days=1)
    next_end = e_date + timedelta(days=span)

    return templates.TemplateResponse(
        request,
        "schedule.html",
        {
            "title": "לוח זמנים",
            "view": view,
            "prev_url": f"/schedule?start={prev_start}&end={prev_end}",
            "next_url": f"/schedule?start={next_start}&end={next_end}",
            "today_url": "/schedule",
            "current_user": "admin" if _is_logged_in(request, settings) else None,
            "edit_mode": _is_logged_in(request, settings),
        },
    )


@router.get("/shift/{shift_date}/{kind}/candidates", response_class=HTMLResponse)
def candidates(
    shift_date: str,
    kind: str,
    request: Request,
    slot: str = Query(...),
    position: int = Query(0),
    q: str | None = Query(None),
    db: Session = Depends(get_db),  # noqa: B008
    _=require_editor(),  # noqa: B008
):
    d = _parse_date(shift_date)
    try:
        kind_enum = ShiftKind(kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="kind") from e
    if slot not in ("commander", "operator"):
        raise HTTPException(status_code=400, detail="slot")

    stmt = select(Person).where(Person.archived.is_(False))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Person.name.like(like))
    candidates = db.execute(stmt.order_by(Person.name)).scalars().all()

    rendered = []
    for p in candidates:
        periods = [{"start_date": pp.start_date, "end_date": pp.end_date}
                   for pp in p.presence_periods]
        check: EligibilityResult = is_eligible(
            {"role": p.role, "archived": p.archived}, periods,
            shift_date=d, kind=kind_enum, slot=slot,
        )
        if not check.eligible:
            continue
        existing = _person_assignments_in_range(
            db, p.id, d - timedelta(days=2), d + timedelta(days=2),
        )
        sev = projected_worst_gap(existing, candidate_kind=kind_enum, candidate_date=d)
        rendered.append({"person": p, "severity": sev})

    return templates.TemplateResponse(
        request, "components/picker.html",
        {
            "shift_date": shift_date,
            "kind": kind,
            "slot": slot,
            "position": position,
            "candidates": rendered,
            "q": q or "",
        },
    )


def _get_or_create_shift(db: Session, d: date_type, kind: ShiftKind) -> Shift:
    shift = db.execute(
        select(Shift).where(Shift.date == d).where(Shift.kind == kind.value)
    ).scalar_one_or_none()
    if shift is None:
        shift = Shift(date=d, kind=kind.value)
        db.add(shift)
        db.flush()
    return shift


def _render_cell(request: Request, view, d: date_type, kind: ShiftKind, edit_mode: bool) -> str:
    day = next(day for day in view.days if day.date == d)
    cell = day.cells[kind.value]
    return templates.get_template("components/cell.html").render(
        {"cell": cell, "edit_mode": edit_mode, "request": request}
    )


def _render_sidebar_oob(request: Request, view) -> str:
    body = templates.get_template("components/sidebar.html").render(
        {"view": view, "request": request}
    )
    return body.replace(
        '<aside class="sidebar"',
        '<aside class="sidebar" hx-swap-oob="outerHTML"',
        1,
    )


@router.post("/shift/{shift_date}/{kind}/assign", response_class=HTMLResponse)
def assign(
    shift_date: str,
    kind: str,
    request: Request,
    slot: str = Form(...),
    position: int = Form(...),
    person_id: int = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),  # noqa: B008
    _=require_editor(),  # noqa: B008
):
    d = _parse_date(shift_date)
    try:
        kind_enum = ShiftKind(kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="kind") from e
    if slot not in ("commander", "operator"):
        raise HTTPException(status_code=400, detail="slot")

    capacity = 1 if (kind_enum == ShiftKind.NIGHT and slot == "operator") else (
        2 if slot == "operator" else 1
    )
    if position < 0 or position >= capacity:
        raise HTTPException(status_code=400, detail="position")

    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person")

    periods = [{"start_date": pp.start_date, "end_date": pp.end_date}
               for pp in person.presence_periods]
    check = is_eligible({"role": person.role, "archived": person.archived}, periods,
                        shift_date=d, kind=kind_enum, slot=slot)
    if not check.eligible:
        raise HTTPException(status_code=400, detail=f"לא כשיר: {check.reason}")

    shift = _get_or_create_shift(db, d, kind_enum)

    existing_slot = db.execute(
        select(ShiftAssignment)
        .where(ShiftAssignment.shift_id == shift.id)
        .where(ShiftAssignment.slot == slot)
        .where(ShiftAssignment.position == position)
    ).scalar_one_or_none()
    if existing_slot is not None:
        db.delete(existing_slot)
        db.flush()

    same_shift = db.execute(
        select(ShiftAssignment).where(ShiftAssignment.shift_id == shift.id)
        .where(ShiftAssignment.person_id == person_id)
    ).scalar_one_or_none()
    if same_shift is not None:
        raise HTTPException(status_code=400, detail="האדם כבר משובץ במשמרת זו")

    a = ShiftAssignment(shift_id=shift.id, person_id=person_id,
                        slot=slot, position=position,
                        note=(note.strip() if note else None) or None)
    db.add(a)
    db.commit()

    span_start = d - timedelta(days=2)
    span_end = d + timedelta(days=14)
    view = build_schedule_view(db, start=span_start, end=span_end)
    cell_html = _render_cell(request, view, d, kind_enum, edit_mode=True)
    sidebar_html = _render_sidebar_oob(request, view)
    return HTMLResponse(content=cell_html + sidebar_html)
