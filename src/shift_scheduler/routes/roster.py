from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from shift_scheduler.auth import require_editor
from shift_scheduler.db import get_db
from shift_scheduler.main import templates
from shift_scheduler.models import Person

router = APIRouter()

VALID_ROLES = {"commander", "operator"}


@router.get("/roster", response_class=HTMLResponse)
def roster_index(request: Request, db: Session = Depends(get_db)):  # noqa: B008
    people = (
        db.execute(
            select(Person).where(Person.archived.is_(False)).order_by(Person.name)
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request, "roster.html", {"title": "סגל", "people": people}
    )


@router.post("/roster")
def roster_create(
    request: Request,
    name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),  # noqa: B008
    _=require_editor(),
):
    name = name.strip()
    if not name:
        return templates.TemplateResponse(
            request,
            "roster.html",
            {"title": "סגל", "people": [], "error": "שם נדרש"},
            status_code=400,
        )
    if role not in VALID_ROLES:
        return templates.TemplateResponse(
            request,
            "roster.html",
            {"title": "סגל", "people": [], "error": "תפקיד לא חוקי"},
            status_code=400,
        )
    person = Person(name=name, role=role)
    db.add(person)
    db.commit()
    return RedirectResponse(url=f"/roster/{person.id}", status_code=302)


@router.get("/roster/{person_id}", response_class=HTMLResponse)
def person_detail(
    person_id: int,
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    return templates.TemplateResponse(
        request,
        "person.html",
        {"title": person.name, "person": person, "periods": person.presence_periods},
    )


@router.post("/roster/{person_id}")
def person_update(
    person_id: int,
    request: Request,
    name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),  # noqa: B008
    _=require_editor(),
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="שם נדרש")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="תפקיד לא חוקי")
    person.name = name
    person.role = role
    db.commit()
    return RedirectResponse(url=f"/roster/{person_id}", status_code=302)


@router.post("/roster/{person_id}/archive")
def person_archive(
    person_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    _=require_editor(),
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    person.archived = True
    db.commit()
    return RedirectResponse(url="/roster", status_code=302)
