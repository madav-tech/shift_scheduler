# Shift Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Hebrew-RTL FastAPI web app that lets a small editor team manually fill three daily shifts on a rolling 14-day timeline, with rest-gap visibility, eligibility checks, single-shared-password auth, and self-hosted deployment behind Cloudflare on a home Linux server.

**Architecture:** Single-process FastAPI on port 2323 rendering server-side Jinja2 templates with HTMX for partial swaps and Alpine.js for the assignment picker; SQLAlchemy 2.0 + SQLite for storage; pure-Python domain layer for shift-time arithmetic, eligibility, and rest calculation; argon2 + signed cookie auth with in-memory rate limiting; run by systemd, fronted by Cloudflare for HTTPS.

**Tech Stack:** Python 3.12+, `uv` (deps + lock), FastAPI, Uvicorn, SQLAlchemy 2.0 (declarative `Mapped`/`mapped_column`), Alembic, SQLite, Jinja2, HTMX 1.9.12, Alpine.js 3.13.5, plain hand-written CSS, `pydantic-settings`, `argon2-cffi`, `itsdangerous`, `click`, `pytest`, `httpx`, `ruff`, `mypy`, `pre-commit`. Spec source: `docs/superpowers/specs/2026-05-20-shift-scheduler-design.md`.

**File map (locked here so later tasks can reference exact paths):**

```
shift_scheduler/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── alembic.ini
├── README.md
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
├── src/shift_scheduler/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory + mounts + router includes
│   ├── config.py            # pydantic-settings BaseSettings
│   ├── db.py                # engine, SessionLocal, get_db dep, Base
│   ├── models.py            # SQLAlchemy 2.0 models (Person, PresencePeriod, Shift, ShiftAssignment, EditLog)
│   ├── shifts.py            # pure domain: shift_window, eligibility, rest gap + severity, projected gap
│   ├── auth.py              # password hashing, session sign/verify, rate limiter, require_editor dep
│   ├── audit.py             # write_log helper
│   ├── cli.py               # click CLI: set-password
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py          # /login, /logout
│   │   ├── roster.py        # /roster, /roster/{id}, /roster/{id}/periods/...
│   │   └── schedule.py      # /, /schedule, /shift/{date}/{kind}/assign|unassign
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── roster.html
│   │   ├── person.html
│   │   ├── schedule.html
│   │   └── components/
│   │       ├── cell.html
│   │       ├── sidebar.html
│   │       └── picker.html
│   └── static/
│       ├── css/app.css
│       └── js/{htmx.min.js, alpine.min.js, sidebar.js}
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_shifts_window.py
│   ├── test_shifts_eligibility.py
│   ├── test_shifts_rest.py
│   ├── test_auth_password.py
│   ├── test_auth_session.py
│   ├── test_auth_ratelimit.py
│   ├── test_routes_login.py
│   ├── test_routes_roster.py
│   ├── test_routes_schedule.py
│   ├── test_routes_assign.py
│   ├── test_audit.py
│   ├── test_cli.py
│   └── test_e2e.py
└── deploy/
    ├── shift-scheduler.service
    └── INSTALL.md
```

**Conventions every task follows:**

- All `pytest` invocations in this plan are run from the project root with `uv run pytest …`.
- All commits use Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`, `refactor:`).
- `git add` lines list only the files actually changed in that task.
- TDD discipline: failing test → run (FAIL) → minimal impl → run (PASS) → commit. Bootstrap-only tasks (no production behaviour) skip the failing-test step but still produce a meaningful smoke check before commit.
- Hebrew strings in templates and assertions are kept literal (UTF-8).

---

## Task 1: Bootstrap project skeleton with uv

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.env.example`
- Create: `src/shift_scheduler/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write `.python-version`**

```
3.12
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "shift-scheduler"
version = "0.1.0"
description = "Hebrew-RTL command-room shift scheduler (Miluim)"
requires-python = ">=3.12"
readme = "README.md"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "pydantic>=2.7",
  "pydantic-settings>=2.4",
  "jinja2>=3.1",
  "python-multipart>=0.0.9",
  "itsdangerous>=2.2",
  "argon2-cffi>=23.1",
  "click>=8.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "httpx>=0.27",
  "ruff>=0.5",
  "mypy>=1.10",
  "pre-commit>=3.7",
]

[project.scripts]
shift-scheduler = "shift_scheduler.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/shift_scheduler"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true
mypy_path = "src"
explicit_package_bases = true
```

- [ ] **Step 3: Write `.env.example`**

```
# Copy to .env and fill in values for local dev.
# Generate ADMIN_PASSWORD_HASH with: uv run python -m shift_scheduler.cli set-password
ADMIN_PASSWORD_HASH=
# Generate SESSION_SECRET with: python -c "import secrets; print(secrets.token_urlsafe(48))"
SESSION_SECRET=replace-me-with-random-48-byte-token
# Local SQLite path; in prod set to /var/lib/shift-scheduler/data.db
DATABASE_URL=sqlite:///./data.db
# Set false for plain-http localhost dev; true behind Cloudflare HTTPS.
COOKIE_SECURE=false
```

- [ ] **Step 4: Create empty package files**

```bash
mkdir -p src/shift_scheduler tests
printf '' > src/shift_scheduler/__init__.py
printf '' > tests/__init__.py
```

- [ ] **Step 5: Install deps and lock**

```bash
uv sync --extra dev
```

Expected: `uv.lock` is created and `.venv/` populated.

- [ ] **Step 6: Smoke check imports**

```bash
uv run python -c "import fastapi, sqlalchemy, alembic, jinja2, argon2, itsdangerous, click; print('ok')"
```

Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .python-version .env.example src/shift_scheduler/__init__.py tests/__init__.py
git commit -m "chore: bootstrap project skeleton with uv and core deps"
```

---

## Task 2: FastAPI skeleton with `/health`

**Files:**
- Create: `src/shift_scheduler/main.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

`tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from shift_scheduler.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_health.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.main'`.

- [ ] **Step 3: Write minimal implementation**

`src/shift_scheduler/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Shift Scheduler")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_health.py -v`

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/main.py tests/test_health.py
git commit -m "feat: FastAPI skeleton with /health endpoint"
```

---

## Task 3: Settings via `pydantic-settings`

**Files:**
- Create: `src/shift_scheduler/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:

```python
from shift_scheduler.config import Settings


def test_settings_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$argon2id$abc")
    monkeypatch.setenv("SESSION_SECRET", "super-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    s = Settings()
    assert s.admin_password_hash == "$argon2id$abc"
    assert s.session_secret == "super-secret"
    assert s.database_url == "sqlite:///./test.db"
    assert s.cookie_secure is False
    assert s.session_max_age_seconds == 12 * 60 * 60
    assert s.timezone == "Asia/Jerusalem"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.config'`.

- [ ] **Step 3: Write minimal implementation**

`src/shift_scheduler/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    admin_password_hash: str = ""
    session_secret: str = "dev-only-change-me"
    database_url: str = "sqlite:///./data.db"
    cookie_secure: bool = True
    session_max_age_seconds: int = 12 * 60 * 60
    timezone: str = "Asia/Jerusalem"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/config.py tests/test_config.py
git commit -m "feat: Settings via pydantic-settings"
```

---

## Task 4: Database engine, session factory, `get_db` dependency

**Files:**
- Create: `src/shift_scheduler/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:

```python
from sqlalchemy import text

from shift_scheduler.db import Base, build_engine, build_session_factory


def test_engine_executes_select_one() -> None:
    engine = build_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


def test_session_factory_yields_working_session() -> None:
    engine = build_engine("sqlite:///:memory:")
    SessionLocal = build_session_factory(engine)
    with SessionLocal() as s:
        assert s.execute(text("SELECT 2")).scalar_one() == 2


def test_base_is_declarative_base() -> None:
    assert hasattr(Base, "metadata")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.db'`.

- [ ] **Step 3: Write minimal implementation**

`src/shift_scheduler/db.py`:

```python
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_db_url: str = "sqlite:///./data.db"


def init_db(url: str) -> None:
    """Record the URL; the engine is built lazily on first get_db() call."""
    global _engine, _SessionLocal, _db_url
    _db_url = url
    _engine = None
    _SessionLocal = None


def _ensure_initialized() -> None:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = build_engine(_db_url)
        _SessionLocal = build_session_factory(_engine)


def get_db() -> Iterator[Session]:
    _ensure_initialized()
    assert _SessionLocal is not None
    with _SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py -v`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/db.py tests/test_db.py
git commit -m "feat: SQLAlchemy 2.0 engine, session factory, get_db dep"
```

---

## Task 5: Models — `Person` and `PresencePeriod`

**Files:**
- Create: `src/shift_scheduler/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from shift_scheduler.db import Base, build_engine, build_session_factory
from shift_scheduler.models import Person, PresencePeriod


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.models'`.

- [ ] **Step 3: Write minimal implementation**

`src/shift_scheduler/models.py`:

```python
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shift_scheduler.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (CheckConstraint("role IN ('commander','operator')", name="ck_person_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    presence_periods: Mapped[list["PresencePeriod"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="PresencePeriod.start_date",
    )


class PresencePeriod(Base):
    __tablename__ = "presence_period"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_period_end_ge_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="presence_periods")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/models.py tests/test_models.py
git commit -m "feat: Person and PresencePeriod models with CHECK constraints"
```

---

## Task 6: Models — `Shift`, `ShiftAssignment`, `EditLog`

**Files:**
- Modify: `src/shift_scheduler/models.py` (append)
- Modify: `tests/test_models.py` (append)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_models.py`:

```python
from datetime import date

from shift_scheduler.models import EditLog, Shift, ShiftAssignment


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
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_models.py -v`

Expected: FAIL — `ImportError: cannot import name 'Shift' from 'shift_scheduler.models'`.

- [ ] **Step 3: Append models to `src/shift_scheduler/models.py`**

```python
from sqlalchemy import UniqueConstraint


class Shift(Base):
    __tablename__ = "shift"
    __table_args__ = (
        CheckConstraint("kind IN ('morning','noon','night')", name="ck_shift_kind"),
        UniqueConstraint("date", "kind", name="uq_shift_date_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)

    assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="shift",
        cascade="all, delete-orphan",
        order_by="ShiftAssignment.slot, ShiftAssignment.position",
    )


class ShiftAssignment(Base):
    __tablename__ = "shift_assignment"
    __table_args__ = (
        CheckConstraint("slot IN ('commander','operator')", name="ck_assign_slot"),
        UniqueConstraint("shift_id", "slot", "position", name="uq_assign_shift_slot_position"),
        UniqueConstraint("shift_id", "person_id", name="uq_assign_shift_person"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("shift.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id"), nullable=False, index=True
    )
    slot: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    shift: Mapped[Shift] = relationship(back_populates="assignments")
    person: Mapped[Person] = relationship()


class EditLog(Base):
    __tablename__ = "edit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_models.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/models.py tests/test_models.py
git commit -m "feat: Shift, ShiftAssignment, EditLog models with uniqueness invariants"
```

---

## Task 7: Alembic init + initial migration

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_initial.py`
- Test: `tests/test_migrations.py`

- [ ] **Step 1: Run alembic init (one-time)**

```bash
uv run alembic init -t generic migrations
```

- [ ] **Step 2: Replace `alembic.ini` script_location and url config**

`alembic.ini` (overwrite the autogenerated file):

```ini
[alembic]
script_location = migrations
prepend_sys_path = src
sqlalchemy.url = sqlite:///./data.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Replace `migrations/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from shift_scheduler.config import get_settings
from shift_scheduler.db import Base
from shift_scheduler import models  # noqa: F401  ensure models are registered

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate the initial migration**

```bash
uv run alembic revision --autogenerate -m "initial schema" --rev-id 0001_initial
```

Expected: `migrations/versions/0001_initial.py` is created. Inspect it; it should `op.create_table` for `person`, `presence_period`, `shift`, `shift_assignment`, `edit_log` with the CHECK and UNIQUE constraints from Task 5/6.

- [ ] **Step 5: Write the failing test**

`tests/test_migrations.py`:

```python
import os
import pathlib
import subprocess
import tempfile


def test_alembic_upgrade_head_creates_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = pathlib.Path(td) / "mig.db"
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{db_path}"
        subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, env=env)
        import sqlite3
        conn = sqlite3.connect(db_path)
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"person", "presence_period", "shift", "shift_assignment", "edit_log"}.issubset(names)
```

- [ ] **Step 6: Run the test — verify it passes**

Run: `uv run pytest tests/test_migrations.py -v`

Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add alembic.ini migrations/ tests/test_migrations.py
git commit -m "feat: Alembic setup with initial schema migration"
```

---

## Task 8: Pure domain — `shift_window(date, kind)` in Asia/Jerusalem (DST-correct)

**Files:**
- Create: `src/shift_scheduler/shifts.py`
- Test: `tests/test_shifts_window.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_shifts_window.py`:

```python
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


def test_dst_spring_forward_night_2026_03_27() -> None:
    # IDT begins Friday before last Sunday of March at 02:00. 2026-03-27 night
    # spans the spring-forward; elapsed real time is 7 hours, not 8.
    start, end = shift_window(date(2026, 3, 27), ShiftKind.NIGHT)
    assert (end - start).total_seconds() == 7 * 3600


def test_dst_fall_back_night_2026_10_24() -> None:
    # IST returns Sunday 2026-10-25 at 02:00 → 01:00. Friday/Saturday night
    # is the night before; pick 2026-10-24 night which spans the fall-back.
    start, end = shift_window(date(2026, 10, 24), ShiftKind.NIGHT)
    assert (end - start).total_seconds() == 9 * 3600


def test_invalid_kind_raises() -> None:
    with pytest.raises(ValueError):
        shift_window(date(2026, 6, 10), "tea-break")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_shifts_window.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.shifts'`.

- [ ] **Step 3: Write the implementation**

`src/shift_scheduler/shifts.py`:

```python
from datetime import date as date_type, datetime, timedelta
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


def shift_window(d: date_type, kind: ShiftKind | str) -> tuple[datetime, datetime]:
    """Return (start_dt, end_dt) for the shift, both timezone-aware in Asia/Jerusalem.

    Wall-clock hours are 06–14 (morning), 14–22 (noon), 22–06 next day (night).
    Around DST transitions the elapsed real time may differ from 8 wall hours.
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
    return start_dt, end_dt
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_shifts_window.py -v`

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/shifts.py tests/test_shifts_window.py
git commit -m "feat: shift_window with DST-correct Asia/Jerusalem times"
```

---

## Task 9: Pure domain — eligibility predicate

**Files:**
- Modify: `src/shift_scheduler/shifts.py` (append)
- Test: `tests/test_shifts_eligibility.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_shifts_eligibility.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_shifts_eligibility.py -v`

Expected: FAIL — `ImportError: cannot import name 'is_eligible' from 'shift_scheduler.shifts'`.

- [ ] **Step 3: Append eligibility helpers to `src/shift_scheduler/shifts.py`**

```python
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    eligible: bool
    reason: str | None = None


def _has_covering_period(periods: Sequence[Mapping], d: date_type) -> Mapping | None:
    for p in periods:
        if p["start_date"] <= d <= p["end_date"]:
            return p
    return None


def is_eligible(
    person: Mapping,
    periods: Sequence[Mapping],
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
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_shifts_eligibility.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/shifts.py tests/test_shifts_eligibility.py
git commit -m "feat: eligibility predicate with arrival-morning and role-slot rules"
```

---

## Task 10: Pure domain — rest gap, severity, chain builder, projected gap

**Files:**
- Modify: `src/shift_scheduler/shifts.py` (append)
- Test: `tests/test_shifts_rest.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_shifts_rest.py`:

```python
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
    sev = projected_worst_gap(existing, candidate_kind=ShiftKind.NOON, candidate_date=date(2026, 6, 10))
    assert sev == RestSeverity.WARNING


def test_projected_worst_gap_no_neighbours_returns_none() -> None:
    sev = projected_worst_gap([], candidate_kind=ShiftKind.MORNING, candidate_date=date(2026, 6, 10))
    assert sev is None
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_shifts_rest.py -v`

Expected: FAIL — `ImportError: cannot import name 'RestSeverity' from 'shift_scheduler.shifts'`.

- [ ] **Step 3: Append rest helpers to `src/shift_scheduler/shifts.py`**

```python
from datetime import datetime as _datetime
from enum import Enum


class RestSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    OK = "ok"


def classify_gap_hours(hours: float) -> RestSeverity:
    if hours < 8:
        return RestSeverity.CRITICAL
    if hours == 8:
        return RestSeverity.WARNING
    return RestSeverity.OK


def rest_gap_hours(prev_end: _datetime, next_start: _datetime) -> float:
    return (next_start - prev_end).total_seconds() / 3600.0


@dataclass(frozen=True, slots=True)
class ChainShift:
    kind: ShiftKind
    date: date_type
    start: _datetime
    end: _datetime


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
    for prev, nxt in zip(expanded, expanded[1:]):
        h = rest_gap_hours(prev.end, nxt.start)
        gaps.append(ChainGap(hours=h, severity=classify_gap_hours(h)))
    return RestChain(shifts=expanded, gaps=gaps)


def projected_worst_gap(
    existing: Sequence[tuple[ShiftKind, date_type]],
    *,
    candidate_kind: ShiftKind,
    candidate_date: date_type,
) -> RestSeverity | None:
    """Compute worst severity of (prev→candidate) and (candidate→next) gaps; None if no neighbours."""
    cand_start, cand_end = shift_window(candidate_date, candidate_kind)
    prev_end: _datetime | None = None
    next_start: _datetime | None = None
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
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_shifts_rest.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/shifts.py tests/test_shifts_rest.py
git commit -m "feat: rest gap classification, chain builder, projected-gap helper"
```

---

## Task 11: Auth library — password hash + verify (argon2)

**Files:**
- Create: `src/shift_scheduler/auth.py`
- Test: `tests/test_auth_password.py`

- [ ] **Step 1: Write the failing test**

`tests/test_auth_password.py`:

```python
from shift_scheduler.auth import hash_password, verify_password


def test_hash_password_returns_argon2_string() -> None:
    h = hash_password("hunter2")
    assert h.startswith("$argon2")


def test_verify_password_accepts_correct() -> None:
    h = hash_password("hunter2")
    assert verify_password(h, "hunter2") is True


def test_verify_password_rejects_wrong() -> None:
    h = hash_password("hunter2")
    assert verify_password(h, "wrong") is False


def test_verify_password_handles_empty_hash() -> None:
    assert verify_password("", "anything") is False
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_auth_password.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.auth'`.

- [ ] **Step 3: Write minimal implementation**

`src/shift_scheduler/auth.py`:

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    if not stored_hash:
        return False
    try:
        return _hasher.verify(stored_hash, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False
```

- [ ] **Step 4: Run test — verify it passes**

Run: `uv run pytest tests/test_auth_password.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/auth.py tests/test_auth_password.py
git commit -m "feat: argon2 password hashing helpers"
```

---

## Task 12: Auth library — signed session cookie

**Files:**
- Modify: `src/shift_scheduler/auth.py` (append)
- Test: `tests/test_auth_session.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_auth_session.py`:

```python
import time

import pytest

from shift_scheduler.auth import SessionExpired, SessionInvalid, sign_session, verify_session


def test_sign_and_verify_roundtrip() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=60)
    assert verify_session(token, secret="s3cret", max_age_seconds=60) == "admin"


def test_verify_rejects_tampered_token() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=60)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    with pytest.raises(SessionInvalid):
        verify_session(tampered, secret="s3cret", max_age_seconds=60)


def test_verify_rejects_wrong_secret() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=60)
    with pytest.raises(SessionInvalid):
        verify_session(token, secret="other", max_age_seconds=60)


def test_verify_rejects_expired() -> None:
    token = sign_session("admin", secret="s3cret", max_age_seconds=1)
    time.sleep(1.1)
    with pytest.raises(SessionExpired):
        verify_session(token, secret="s3cret", max_age_seconds=1)
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_auth_session.py -v`

Expected: FAIL — `ImportError: cannot import name 'sign_session' from 'shift_scheduler.auth'`.

- [ ] **Step 3: Append session helpers to `src/shift_scheduler/auth.py`**

```python
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SESSION_SALT = "shift-scheduler.session.v1"


class SessionInvalid(Exception):
    pass


class SessionExpired(Exception):
    pass


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret, salt=_SESSION_SALT)


def sign_session(subject: str, *, secret: str, max_age_seconds: int) -> str:
    """Sign a token carrying `subject` (e.g. 'admin'). max_age_seconds is checked at verify time."""
    return _serializer(secret).dumps({"sub": subject})


def verify_session(token: str, *, secret: str, max_age_seconds: int) -> str:
    try:
        payload = _serializer(secret).loads(token, max_age=max_age_seconds)
    except SignatureExpired as e:
        raise SessionExpired(str(e)) from e
    except BadSignature as e:
        raise SessionInvalid(str(e)) from e
    if not isinstance(payload, dict) or "sub" not in payload:
        raise SessionInvalid("malformed payload")
    return str(payload["sub"])
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_auth_session.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/auth.py tests/test_auth_session.py
git commit -m "feat: signed session token via itsdangerous with explicit expiry"
```

---

## Task 13: Auth library — in-memory rate limiter

**Files:**
- Modify: `src/shift_scheduler/auth.py` (append)
- Test: `tests/test_auth_ratelimit.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_auth_ratelimit.py`:

```python
from shift_scheduler.auth import LoginRateLimiter


def test_first_failures_are_allowed() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    assert rl.is_locked("1.1.1.1", now=0.0) is False
    for i in range(4):
        rl.register_failure("1.1.1.1", now=float(i))
    assert rl.is_locked("1.1.1.1", now=4.0) is False


def test_fifth_failure_locks_out() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for i in range(5):
        rl.register_failure("1.1.1.1", now=float(i))
    assert rl.is_locked("1.1.1.1", now=5.0) is True


def test_lockout_clears_after_window() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for i in range(5):
        rl.register_failure("1.1.1.1", now=float(i))
    assert rl.is_locked("1.1.1.1", now=905.0) is False


def test_success_clears_history() -> None:
    rl = LoginRateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for i in range(4):
        rl.register_failure("1.1.1.1", now=float(i))
    rl.register_success("1.1.1.1")
    for i in range(4):
        rl.register_failure("1.1.1.1", now=10.0 + i)
    assert rl.is_locked("1.1.1.1", now=20.0) is False
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_auth_ratelimit.py -v`

Expected: FAIL — `ImportError: cannot import name 'LoginRateLimiter' from 'shift_scheduler.auth'`.

- [ ] **Step 3: Append rate limiter to `src/shift_scheduler/auth.py`**

```python
import time
from collections import deque
from threading import Lock


class LoginRateLimiter:
    """Per-IP failed-login tracker with sliding-window lockout. Resets on process restart."""

    def __init__(self, *, max_failures: int = 5, window_seconds: int = 15 * 60,
                 lockout_seconds: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _now(self, now: float | None) -> float:
        return time.monotonic() if now is None else now

    def _purge(self, key: str, now: float) -> None:
        dq = self._failures.get(key)
        if dq is None:
            return
        cutoff = now - max(self.window_seconds, self.lockout_seconds)
        while dq and dq[0] < cutoff:
            dq.popleft()
        if not dq:
            del self._failures[key]

    def register_failure(self, key: str, *, now: float | None = None) -> None:
        t = self._now(now)
        with self._lock:
            self._failures.setdefault(key, deque()).append(t)
            self._purge(key, t)

    def register_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def is_locked(self, key: str, *, now: float | None = None) -> bool:
        t = self._now(now)
        with self._lock:
            self._purge(key, t)
            dq = self._failures.get(key)
            if dq is None:
                return False
            return len(dq) >= self.max_failures
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_auth_ratelimit.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/auth.py tests/test_auth_ratelimit.py
git commit -m "feat: in-memory per-IP login rate limiter"
```

---

## Task 14: Auth dependency `require_editor` + client IP helper

**Files:**
- Modify: `src/shift_scheduler/auth.py` (append)
- Test: `tests/test_auth_require.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_auth_require.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    client_ip,
    require_editor,
    sign_session,
)
from shift_scheduler.config import Settings


def _build_app(settings: Settings) -> FastAPI:
    app = FastAPI()

    from shift_scheduler.config import get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/secret")
    def secret(_=require_editor()) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.get("/whoami")
    def whoami(request: Request) -> PlainTextResponse:
        return PlainTextResponse(client_ip(request))

    return app


def test_require_editor_redirects_without_cookie() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    client = TestClient(app, follow_redirects=False)
    r = client.get("/secret")
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login")


def test_require_editor_allows_with_valid_cookie() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client = TestClient(app, cookies={SESSION_COOKIE_NAME: token})
    r = client.get("/secret")
    assert r.status_code == 200
    assert r.text == "ok"


def test_client_ip_prefers_cf_connecting_ip() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    client = TestClient(app)
    r = client.get("/whoami", headers={"CF-Connecting-IP": "9.9.9.9"})
    assert r.text == "9.9.9.9"


def test_client_ip_falls_back_to_remote_addr() -> None:
    settings = Settings(session_secret="t", admin_password_hash="x", cookie_secure=False)
    app = _build_app(settings)
    client = TestClient(app)
    r = client.get("/whoami")
    assert r.text  # non-empty (TestClient supplies "testclient")
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_auth_require.py -v`

Expected: FAIL — `ImportError: cannot import name 'require_editor'`.

- [ ] **Step 3: Append dependency + ip helper to `src/shift_scheduler/auth.py`**

```python
from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException

from shift_scheduler.config import Settings, get_settings

SESSION_COOKIE_NAME = "ss_session"


def client_ip(request: Request) -> str:
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf
    if request.client is None:
        return ""
    return request.client.host


class _RedirectToLogin(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=302, detail="login required")


def _current_subject(request: Request, settings: Settings) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return verify_session(token, secret=settings.session_secret,
                              max_age_seconds=settings.session_max_age_seconds)
    except (SessionInvalid, SessionExpired):
        return None


def require_editor():
    """FastAPI dependency: 302 to /login when not authenticated, otherwise pass through."""

    def _dep(request: Request, settings: Settings = Depends(get_settings)) -> str:
        sub = _current_subject(request, settings)
        if sub is None:
            raise _RedirectToLogin()
        return sub

    return Depends(_dep)


def install_auth_exception_handler(app) -> None:
    @app.exception_handler(_RedirectToLogin)
    async def _handle(_request: Request, _exc: _RedirectToLogin):  # type: ignore[no-untyped-def]
        return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_auth_require.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/auth.py tests/test_auth_require.py
git commit -m "feat: require_editor FastAPI dependency + client_ip helper"
```

---

## Task 15: Test infrastructure — `conftest.py` with TestClient + in-memory DB

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from shift_scheduler import db as db_module
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.db import Base, build_engine, build_session_factory


@pytest.fixture
def settings() -> Settings:
    return Settings(
        admin_password_hash="",  # set per-test if needed
        session_secret="test-secret",
        database_url="sqlite:///:memory:",
        cookie_secure=False,
        session_max_age_seconds=3600,
    )


@pytest.fixture
def engine_and_session(settings: Settings):
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = build_session_factory(engine)
    try:
        yield engine, SessionLocal
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(settings: Settings, engine_and_session) -> Iterator[TestClient]:
    from shift_scheduler.main import build_app

    _, SessionLocal = engine_and_session

    def _override_get_db():
        with SessionLocal() as s:
            yield s

    app = build_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[db_module.get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 2: Smoke check — existing tests still pass with conftest in place**

Run: `uv run pytest -q`

Expected: all tests written through Task 14 still pass; no import errors from the new conftest. (`build_app` is imported lazily inside the `client` fixture, so it does not break collection before Task 16.)

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: shared TestClient + in-memory SQLite fixture"
```

---

## Task 16: App factory, static mount, Jinja2, base template, plain CSS

**Files:**
- Modify: `src/shift_scheduler/main.py` (rewrite)
- Create: `src/shift_scheduler/templates/base.html`
- Create: `src/shift_scheduler/static/css/app.css`
- Create: `src/shift_scheduler/static/js/htmx.min.js` (downloaded)
- Create: `src/shift_scheduler/static/js/alpine.min.js` (downloaded)
- Create: `src/shift_scheduler/static/js/sidebar.js` (placeholder, populated in Task 23)
- Create: `tests/test_app_factory.py`

- [ ] **Step 1: Download HTMX and Alpine.js into the repo (no build step)**

```bash
mkdir -p src/shift_scheduler/static/{css,js} src/shift_scheduler/templates/components
curl -fsSL https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js \
  -o src/shift_scheduler/static/js/htmx.min.js
curl -fsSL https://cdn.jsdelivr.net/npm/alpinejs@3.13.5/dist/cdn.min.js \
  -o src/shift_scheduler/static/js/alpine.min.js
printf '/* populated in Task 23 */\n' > src/shift_scheduler/static/js/sidebar.js
```

Expected: both files non-empty (`wc -c src/shift_scheduler/static/js/*.js` ≥ 1000 each).

- [ ] **Step 2: Write the failing test**

`tests/test_app_factory.py`:

```python
def test_root_redirects_to_schedule(client) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 or r.status_code == 302
    assert r.headers["location"].endswith("/schedule")


def test_health_still_works(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_static_css_is_served(client) -> None:
    r = client.get("/static/css/app.css")
    assert r.status_code == 200
    assert "html" in r.text or "body" in r.text


def test_base_template_is_rtl(client) -> None:
    # /login is the first concrete page that extends base.html (added in Task 17),
    # but base.html itself is rendered indirectly here through any page using it.
    # Until Task 17, exercise base via the placeholder /schedule landing.
    r = client.get("/schedule", follow_redirects=False)
    # Either renders (200) or redirects to /login (302) depending on auth state;
    # both are acceptable. If 200, body must declare RTL.
    if r.status_code == 200:
        assert 'dir="rtl"' in r.text
        assert 'lang="he"' in r.text
```

- [ ] **Step 3: Run test — verify it fails**

Run: `uv run pytest tests/test_app_factory.py -v`

Expected: FAIL — `build_app` not found, redirect missing, static not mounted.

- [ ] **Step 4: Replace `src/shift_scheduler/main.py`**

```python
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    SessionExpired,
    SessionInvalid,
    install_auth_exception_handler,
    verify_session,
)
from shift_scheduler.config import get_settings
from shift_scheduler.db import init_db

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


def _current_user_processor(request: Request) -> dict[str, str | None]:
    settings = get_settings()
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return {"current_user": None}
    try:
        sub = verify_session(
            token,
            secret=settings.session_secret,
            max_age_seconds=settings.session_max_age_seconds,
        )
        return {"current_user": sub}
    except (SessionInvalid, SessionExpired):
        return {"current_user": None}


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
    context_processors=[_current_user_processor],
)


def build_app() -> FastAPI:
    settings = get_settings()
    init_db(settings.database_url)

    app = FastAPI(title="Shift Scheduler", default_response_class=None)
    install_auth_exception_handler(app)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/schedule", status_code=302)

    @app.get("/schedule")
    def schedule_placeholder(request: Request):
        # Replaced in Task 22 with the real handler.
        return templates.TemplateResponse(request, "base.html",
                                          {"title": "לוח זמנים", "content": ""})

    return app


app = build_app()
```

- [ ] **Step 5: Write `src/shift_scheduler/templates/base.html`**

```html
<!doctype html>
<html dir="rtl" lang="he">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title|default('לוח שיבוץ') }}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='css/app.css') }}">
    <script src="{{ url_for('static', path='js/htmx.min.js') }}" defer></script>
    <script src="{{ url_for('static', path='js/alpine.min.js') }}" defer></script>
  </head>
  <body>
    <header class="topbar">
      <a href="/schedule" class="brand">לוח שיבוץ</a>
      <nav>
        <a href="/schedule">לוח זמנים</a>
        <a href="/roster">סגל</a>
        {% if current_user %}
          <form method="post" action="/logout" class="inline">
            <button type="submit">התנתק</button>
          </form>
        {% else %}
          <a href="/login">התחברות</a>
        {% endif %}
      </nav>
    </header>
    <main id="main-content">
      {% block content %}{{ content|safe if content }}{% endblock %}
    </main>
    <script src="{{ url_for('static', path='js/sidebar.js') }}" defer></script>
  </body>
</html>
```

- [ ] **Step 6: Write `src/shift_scheduler/static/css/app.css`**

```css
:root {
  --bg: #f6f5f2;
  --fg: #1c1c1c;
  --muted: #6b6b6b;
  --border: #d8d4cc;
  --accent: #2b6cb0;
  --critical-bg: #fde2e2;
  --critical-fg: #9a1f1f;
  --warning-bg: #fff3cd;
  --warning-fg: #8a6100;
  --ok-bg: #e1f3e3;
  --ok-fg: #265d2b;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg);
  font-family: system-ui, "Segoe UI", "Arial Hebrew", Tahoma, sans-serif; font-size: 15px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.topbar { display: flex; align-items: center; gap: 1rem; padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border); background: white; }
.topbar .brand { font-weight: 700; }
.topbar nav { margin-inline-start: auto; display: flex; gap: 0.75rem; align-items: center; }
.topbar form.inline { display: inline; }
.topbar button { background: none; border: 1px solid var(--border); border-radius: 4px;
  padding: 0.25rem 0.6rem; cursor: pointer; font: inherit; }

main { padding: 1rem; }

.schedule-grid { display: grid; grid-template-columns: 8rem repeat(3, 1fr); gap: 0.4rem;
  align-items: stretch; }
.schedule-grid .col-header { font-weight: 600; padding: 0.4rem; border-bottom: 1px solid var(--border); }
.schedule-grid .day-label { padding: 0.4rem; font-weight: 600; }
.cell { background: white; border: 1px solid var(--border); border-radius: 6px;
  padding: 0.4rem; min-height: 4.5rem; }
.cell.tint-critical { background: var(--critical-bg); border-color: #f0b1b1; }
.cell.tint-warning { background: var(--warning-bg); border-color: #e3c98a; }
.cell .slot { display: flex; align-items: center; gap: 0.4rem; padding: 0.15rem 0; }
.cell .slot.empty { color: var(--muted); }
.cell .commander::before { content: "★ "; color: #c19a00; }

.layout { display: grid; grid-template-columns: 1fr 18rem; gap: 1rem; }
.layout.sidebar-collapsed { grid-template-columns: 1fr 2rem; }
.sidebar { background: white; border: 1px solid var(--border); border-radius: 6px;
  padding: 0.6rem; max-height: 80vh; overflow: auto; }
.sidebar header { display: flex; align-items: center; gap: 0.5rem; }
.sidebar .toggle { margin-inline-start: auto; }
.sidebar.collapsed { padding: 0.3rem; }
.sidebar.collapsed .body { display: none; }
.sidebar .person-row { padding: 0.3rem 0; border-bottom: 1px dashed var(--border); }
.sidebar .person-row:last-child { border-bottom: 0; }
.chip { display: inline-block; padding: 0 0.4rem; border-radius: 999px; font-size: 0.85em; }
.chip.shift { background: #eef2f7; }
.chip.gap.critical { background: var(--critical-bg); color: var(--critical-fg); }
.chip.gap.warning { background: var(--warning-bg); color: var(--warning-fg); }
.chip.gap.ok { background: var(--ok-bg); color: var(--ok-fg); }

.picker { position: absolute; background: white; border: 1px solid var(--border);
  border-radius: 6px; padding: 0.5rem; box-shadow: 0 4px 14px rgba(0,0,0,0.08);
  min-width: 16rem; max-height: 18rem; overflow: auto; z-index: 50; }
.picker input[type="search"] { width: 100%; padding: 0.3rem; border: 1px solid var(--border);
  border-radius: 4px; font: inherit; margin-bottom: 0.35rem; }
.picker .candidate { display: flex; gap: 0.5rem; padding: 0.2rem 0.3rem; cursor: pointer;
  border-radius: 4px; align-items: center; }
.picker .candidate:hover { background: #f0f0ee; }
.picker .gap-projection { margin-inline-start: auto; font-size: 0.85em; }

form.stack > * { display: block; margin-block: 0.5rem; }
input[type="text"], input[type="password"], input[type="date"], select, textarea {
  padding: 0.35rem; border: 1px solid var(--border); border-radius: 4px; font: inherit; }
button.primary { background: var(--accent); color: white; border: 0; border-radius: 4px;
  padding: 0.4rem 0.9rem; cursor: pointer; }
.error { color: var(--critical-fg); background: var(--critical-bg); padding: 0.4rem 0.6rem;
  border-radius: 4px; }
table.roster { width: 100%; border-collapse: collapse; background: white; }
table.roster th, table.roster td { padding: 0.4rem; border-bottom: 1px solid var(--border); text-align: start; }
```

- [ ] **Step 7: Run test — verify it passes**

Run: `uv run pytest tests/test_app_factory.py -v`

Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add src/shift_scheduler/main.py src/shift_scheduler/templates/base.html \
        src/shift_scheduler/static/css/app.css src/shift_scheduler/static/js \
        tests/test_app_factory.py
git commit -m "feat: app factory, static mount, Jinja2, RTL base template, plain CSS"
```

---

## Task 17: Login GET/POST, logout, `login.html`

**Files:**
- Create: `src/shift_scheduler/routes/__init__.py`
- Create: `src/shift_scheduler/routes/auth.py`
- Create: `src/shift_scheduler/templates/login.html`
- Modify: `src/shift_scheduler/main.py` (include router)
- Test: `tests/test_routes_login.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_routes_login.py`:

```python
import pytest

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password
from shift_scheduler.config import Settings, get_settings


@pytest.fixture
def authed_settings(settings: Settings) -> Settings:
    settings.admin_password_hash = hash_password("hunter2")
    return settings


def test_get_login_renders_form(client) -> None:
    r = client.get("/login")
    assert r.status_code == 200
    assert "סיסמה" in r.text
    assert "name=\"password\"" in r.text


def test_post_login_wrong_password_shows_error(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    r = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert r.status_code == 200
    assert "סיסמה שגויה" in r.text
    assert SESSION_COOKIE_NAME not in r.cookies


def test_post_login_correct_password_sets_cookie_and_redirects(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    r = client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/schedule"
    assert SESSION_COOKIE_NAME in r.cookies


def test_post_logout_clears_cookie_and_redirects(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    client.post("/login", data={"password": "hunter2"})
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"
    assert r.cookies.get(SESSION_COOKIE_NAME) in (None, "")


def test_rate_limiter_locks_after_5_failures(client, authed_settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: authed_settings
    for _ in range(5):
        client.post("/login", data={"password": "wrong"})
    r = client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert r.status_code == 200
    assert "נעול" in r.text or "נסה שוב מאוחר" in r.text
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_routes_login.py -v`

Expected: FAIL — `/login` 404 / no router registered.

- [ ] **Step 3: Write `src/shift_scheduler/routes/__init__.py`**

```python
```

- [ ] **Step 4: Write `src/shift_scheduler/routes/auth.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from shift_scheduler.auth import (
    LoginRateLimiter,
    SESSION_COOKIE_NAME,
    client_ip,
    sign_session,
    verify_password,
)
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.main import templates

router = APIRouter()
rate_limiter = LoginRateLimiter()


@router.get("/login")
def get_login(request: Request):
    return templates.TemplateResponse(request, "login.html",
                                      {"title": "התחברות", "error": None})


@router.post("/login")
def post_login(
    request: Request,
    password: str = Form(...),
    settings: Settings = Depends(get_settings),
):
    ip = client_ip(request)
    if rate_limiter.is_locked(ip):
        return templates.TemplateResponse(
            request, "login.html",
            {"title": "התחברות", "error": "החשבון נעול זמנית — נסה שוב מאוחר יותר"},
            status_code=200,
        )

    if not verify_password(settings.admin_password_hash, password):
        rate_limiter.register_failure(ip)
        return templates.TemplateResponse(
            request, "login.html",
            {"title": "התחברות", "error": "סיסמה שגויה"},
            status_code=200,
        )

    rate_limiter.register_success(ip)
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    response = RedirectResponse(url="/schedule", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
def post_logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
```

- [ ] **Step 5: Write `src/shift_scheduler/templates/login.html`**

```html
{% extends "base.html" %}
{% block content %}
<section class="login">
  <h1>התחברות</h1>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="post" action="/login" class="stack">
    <label>
      סיסמה
      <input type="password" name="password" autofocus required>
    </label>
    <button type="submit" class="primary">כניסה</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 6: Wire the router in `src/shift_scheduler/main.py`**

Inside `build_app()`, after the `@app.get("/")` registration, add:

```python
    from shift_scheduler.routes import auth as auth_routes
    app.include_router(auth_routes.router)
```

- [ ] **Step 7: Run tests — verify pass**

Run: `uv run pytest tests/test_routes_login.py -v`

Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
git add src/shift_scheduler/routes/ src/shift_scheduler/templates/login.html \
        src/shift_scheduler/main.py tests/test_routes_login.py
git commit -m "feat: /login + /logout with argon2 verify, signed cookie, rate limit"
```

---

## Task 18: Roster index — `GET /roster` + create person

**Files:**
- Create: `src/shift_scheduler/routes/roster.py`
- Create: `src/shift_scheduler/templates/roster.html`
- Modify: `src/shift_scheduler/main.py` (include router)
- Test: `tests/test_routes_roster.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_routes_roster.py`:

```python
from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def test_roster_index_public_read(client) -> None:
    r = client.get("/roster")
    assert r.status_code == 200
    assert "סגל" in r.text


def test_roster_create_requires_auth(client) -> None:
    r = client.post("/roster", data={"name": "דן", "role": "operator"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login")


def test_roster_create_persists_person(client, settings) -> None:
    _login(client, settings)
    r = client.post("/roster", data={"name": "דן", "role": "operator"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("/roster/")
    listing = client.get("/roster")
    assert "דן" in listing.text


def test_roster_create_rejects_invalid_role(client, settings) -> None:
    _login(client, settings)
    r = client.post("/roster", data={"name": "דן", "role": "wizard"})
    assert r.status_code == 400
    assert "תפקיד" in r.text
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_routes_roster.py -v`

Expected: FAIL — `/roster` returns 404.

- [ ] **Step 3: Write `src/shift_scheduler/routes/roster.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
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
def roster_index(request: Request, db: Session = Depends(get_db)):
    people = db.execute(
        select(Person).where(Person.archived.is_(False)).order_by(Person.name)
    ).scalars().all()
    return templates.TemplateResponse(request, "roster.html",
                                      {"title": "סגל", "people": people})


@router.post("/roster")
def roster_create(
    request: Request,
    name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    _=require_editor(),
):
    name = name.strip()
    if not name:
        return templates.TemplateResponse(
            request, "roster.html",
            {"title": "סגל", "people": [], "error": "שם נדרש"}, status_code=400,
        )
    if role not in VALID_ROLES:
        return templates.TemplateResponse(
            request, "roster.html",
            {"title": "סגל", "people": [], "error": "תפקיד לא חוקי"}, status_code=400,
        )
    person = Person(name=name, role=role)
    db.add(person)
    db.commit()
    return RedirectResponse(url=f"/roster/{person.id}", status_code=302)
```

- [ ] **Step 4: Write `src/shift_scheduler/templates/roster.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>סגל</h1>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<form method="post" action="/roster" class="stack">
  <label>שם <input type="text" name="name" required></label>
  <label>תפקיד
    <select name="role">
      <option value="operator">מפעיל/ה</option>
      <option value="commander">מפקד/ת</option>
    </select>
  </label>
  <button type="submit" class="primary">הוסף</button>
</form>

<table class="roster">
  <thead><tr><th>שם</th><th>תפקיד</th><th></th></tr></thead>
  <tbody>
    {% for p in people %}
      <tr>
        <td><a href="/roster/{{ p.id }}">{{ p.name }}</a></td>
        <td>{{ "מפקד/ת" if p.role == "commander" else "מפעיל/ה" }}</td>
        <td><a href="/roster/{{ p.id }}">פרטים</a></td>
      </tr>
    {% else %}
      <tr><td colspan="3">אין אנשים בסגל</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 5: Wire the router in `src/shift_scheduler/main.py`**

Inside `build_app()`, after the auth router include:

```python
    from shift_scheduler.routes import roster as roster_routes
    app.include_router(roster_routes.router)
```

- [ ] **Step 6: Run tests — verify pass**

Run: `uv run pytest tests/test_routes_roster.py -v`

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add src/shift_scheduler/routes/roster.py \
        src/shift_scheduler/templates/roster.html \
        src/shift_scheduler/main.py tests/test_routes_roster.py
git commit -m "feat: /roster index + create person"
```

---

## Task 19: Roster — update + archive + person detail page

**Files:**
- Modify: `src/shift_scheduler/routes/roster.py` (append routes)
- Create: `src/shift_scheduler/templates/person.html`
- Modify: `tests/test_routes_roster.py` (append)

- [ ] **Step 1: Append the failing tests** to `tests/test_routes_roster.py`:

```python
def test_person_detail_shows_name(client, settings) -> None:
    _login(client, settings)
    create = client.post("/roster", data={"name": "דן", "role": "operator"},
                         follow_redirects=False)
    pid = create.headers["location"].rsplit("/", 1)[-1]
    r = client.get(f"/roster/{pid}")
    assert r.status_code == 200
    assert "דן" in r.text


def test_person_update_changes_name_and_role(client, settings) -> None:
    _login(client, settings)
    create = client.post("/roster", data={"name": "דן", "role": "operator"},
                         follow_redirects=False)
    pid = create.headers["location"].rsplit("/", 1)[-1]
    r = client.post(f"/roster/{pid}", data={"name": "דניאל", "role": "commander"},
                    follow_redirects=False)
    assert r.status_code == 302
    after = client.get(f"/roster/{pid}")
    assert "דניאל" in after.text
    assert 'value="commander" selected' in after.text


def test_person_archive_hides_from_index(client, settings) -> None:
    _login(client, settings)
    create = client.post("/roster", data={"name": "ליאור", "role": "operator"},
                         follow_redirects=False)
    pid = create.headers["location"].rsplit("/", 1)[-1]
    r = client.post(f"/roster/{pid}/archive", follow_redirects=False)
    assert r.status_code == 302
    listing = client.get("/roster")
    assert "ליאור" not in listing.text


def test_person_detail_404_when_missing(client, settings) -> None:
    _login(client, settings)
    r = client.get("/roster/9999")
    assert r.status_code == 404
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_routes_roster.py -v`

Expected: FAIL — detail/update/archive routes return 404.

- [ ] **Step 3: Append routes to `src/shift_scheduler/routes/roster.py`**

```python
from fastapi import HTTPException


@router.get("/roster/{person_id}", response_class=HTMLResponse)
def person_detail(person_id: int, request: Request, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    return templates.TemplateResponse(
        request, "person.html",
        {"title": person.name, "person": person, "periods": person.presence_periods},
    )


@router.post("/roster/{person_id}")
def person_update(
    person_id: int,
    request: Request,
    name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    _=require_editor(),
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    person.archived = True
    db.commit()
    return RedirectResponse(url="/roster", status_code=302)
```

- [ ] **Step 4: Write `src/shift_scheduler/templates/person.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ person.name }}</h1>
<form method="post" action="/roster/{{ person.id }}" class="stack">
  <label>שם <input type="text" name="name" value="{{ person.name }}" required></label>
  <label>תפקיד
    <select name="role">
      <option value="operator" {% if person.role == "operator" %}selected{% endif %}>מפעיל/ה</option>
      <option value="commander" {% if person.role == "commander" %}selected{% endif %}>מפקד/ת</option>
    </select>
  </label>
  <button type="submit" class="primary">שמור</button>
</form>

<form method="post" action="/roster/{{ person.id }}/archive" class="stack">
  <button type="submit">ארכון</button>
</form>

<h2>תקופות נוכחות</h2>
<form method="post" action="/roster/{{ person.id }}/periods" class="stack">
  <label>מתאריך <input type="date" name="start_date" required></label>
  <label>עד תאריך <input type="date" name="end_date" required></label>
  <label>הערה <input type="text" name="note"></label>
  <button type="submit" class="primary">הוסף תקופה</button>
</form>

<ul class="periods">
  {% for pp in periods %}
  <li>
    {{ pp.start_date }} → {{ pp.end_date }}
    {% if pp.note %}— {{ pp.note }}{% endif %}
    <form method="post" action="/roster/{{ person.id }}/periods/{{ pp.id }}/delete" class="inline">
      <button type="submit">מחק</button>
    </form>
  </li>
  {% else %}
  <li>אין תקופות נוכחות</li>
  {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 5: Run — verify pass**

Run: `uv run pytest tests/test_routes_roster.py -v`

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add src/shift_scheduler/routes/roster.py \
        src/shift_scheduler/templates/person.html \
        tests/test_routes_roster.py
git commit -m "feat: person detail, update, archive routes"
```

---

## Task 20: Presence periods CRUD

**Files:**
- Modify: `src/shift_scheduler/routes/roster.py` (append routes)
- Modify: `tests/test_routes_roster.py` (append)

- [ ] **Step 1: Append the failing tests**

```python
from datetime import date


def _create_person(client, settings, name="דן", role="operator") -> int:
    _login(client, settings)
    r = client.post("/roster", data={"name": name, "role": role}, follow_redirects=False)
    return int(r.headers["location"].rsplit("/", 1)[-1])


def test_create_period_persists(client, settings) -> None:
    pid = _create_person(client, settings)
    r = client.post(f"/roster/{pid}/periods",
                    data={"start_date": "2026-06-01", "end_date": "2026-06-10", "note": "תורנות"},
                    follow_redirects=False)
    assert r.status_code == 302
    detail = client.get(f"/roster/{pid}")
    assert "2026-06-01" in detail.text
    assert "2026-06-10" in detail.text
    assert "תורנות" in detail.text


def test_create_period_rejects_inverted_dates(client, settings) -> None:
    pid = _create_person(client, settings)
    r = client.post(f"/roster/{pid}/periods",
                    data={"start_date": "2026-06-10", "end_date": "2026-06-01"},
                    follow_redirects=False)
    assert r.status_code == 400


def test_update_period_changes_dates(client, settings) -> None:
    pid = _create_person(client, settings)
    client.post(f"/roster/{pid}/periods",
                data={"start_date": "2026-06-01", "end_date": "2026-06-05"})
    detail = client.get(f"/roster/{pid}")
    # find period id from form action
    import re
    m = re.search(rf"/roster/{pid}/periods/(\d+)/delete", detail.text)
    assert m
    period_id = int(m.group(1))
    r = client.post(f"/roster/{pid}/periods/{period_id}",
                    data={"start_date": "2026-06-02", "end_date": "2026-06-09", "note": "עודכן"},
                    follow_redirects=False)
    assert r.status_code == 302
    after = client.get(f"/roster/{pid}")
    assert "2026-06-09" in after.text


def test_delete_period_removes_it(client, settings) -> None:
    pid = _create_person(client, settings)
    client.post(f"/roster/{pid}/periods",
                data={"start_date": "2026-06-01", "end_date": "2026-06-05"})
    detail = client.get(f"/roster/{pid}")
    import re
    period_id = int(re.search(rf"/roster/{pid}/periods/(\d+)/delete", detail.text).group(1))
    r = client.post(f"/roster/{pid}/periods/{period_id}/delete", follow_redirects=False)
    assert r.status_code == 302
    after = client.get(f"/roster/{pid}")
    assert "2026-06-01" not in after.text
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_routes_roster.py -v`

Expected: FAIL — period routes return 404.

- [ ] **Step 3: Append routes to `src/shift_scheduler/routes/roster.py`**

```python
from datetime import date as date_type, datetime

from shift_scheduler.models import PresencePeriod


def _parse_date(s: str) -> date_type:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"תאריך לא תקין: {s}") from e


@router.post("/roster/{person_id}/periods")
def period_create(
    person_id: int,
    start_date: str = Form(...),
    end_date: str = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    _=require_editor(),
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if ed < sd:
        raise HTTPException(status_code=400, detail="תאריך סיום קטן מתאריך התחלה")
    pp = PresencePeriod(person_id=person_id, start_date=sd, end_date=ed,
                        note=(note.strip() if note else None) or None)
    db.add(pp)
    db.commit()
    return RedirectResponse(url=f"/roster/{person_id}", status_code=302)


@router.post("/roster/{person_id}/periods/{period_id}")
def period_update(
    person_id: int,
    period_id: int,
    start_date: str = Form(...),
    end_date: str = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    _=require_editor(),
):
    pp = db.get(PresencePeriod, period_id)
    if pp is None or pp.person_id != person_id:
        raise HTTPException(status_code=404, detail="period not found")
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if ed < sd:
        raise HTTPException(status_code=400, detail="תאריך סיום קטן מתאריך התחלה")
    pp.start_date = sd
    pp.end_date = ed
    pp.note = (note.strip() if note else None) or None
    db.commit()
    return RedirectResponse(url=f"/roster/{person_id}", status_code=302)


@router.post("/roster/{person_id}/periods/{period_id}/delete")
def period_delete(
    person_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    _=require_editor(),
):
    pp = db.get(PresencePeriod, period_id)
    if pp is None or pp.person_id != person_id:
        raise HTTPException(status_code=404, detail="period not found")
    db.delete(pp)
    db.commit()
    return RedirectResponse(url=f"/roster/{person_id}", status_code=302)
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/test_routes_roster.py -v`

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/routes/roster.py tests/test_routes_roster.py
git commit -m "feat: presence period create/update/delete"
```

---

## Task 21: Schedule view-model service

**Files:**
- Create: `src/shift_scheduler/services.py`
- Test: `tests/test_services_schedule.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_services_schedule.py`:

```python
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
    session.add_all([
        ShiftAssignment(shift_id=s_noon.id, person_id=p.id, slot="commander", position=0),
        ShiftAssignment(shift_id=s_morn.id, person_id=p.id, slot="commander", position=0),
    ])
    session.add(PresencePeriod(person_id=p.id, start_date=date(2026, 5, 1),
                               end_date=date(2026, 6, 30)))
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
    session.add_all([
        PresencePeriod(person_id=p_in.id, start_date=date(2026, 6, 5), end_date=date(2026, 6, 8)),
        PresencePeriod(person_id=p_out.id, start_date=date(2026, 7, 1), end_date=date(2026, 7, 3)),
        PresencePeriod(person_id=p_arch.id, start_date=date(2026, 6, 5), end_date=date(2026, 6, 8)),
    ])
    session.commit()

    view = build_schedule_view(session, start=date(2026, 6, 1), end=date(2026, 6, 14))
    names = [row.person.name for row in view.sidebar_rows]
    assert "In" in names
    assert "Out" not in names
    assert "Arch" not in names
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_services_schedule.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.services'`.

- [ ] **Step 3: Write `src/shift_scheduler/services.py`**

```python
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
    nearby = _person_assignments_in_range(db, person_id, d - timedelta(days=2), d + timedelta(days=2))
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
    shifts = db.execute(
        select(Shift)
        .where(Shift.date >= start)
        .where(Shift.date <= end)
        .options(joinedload(Shift.assignments).joinedload(ShiftAssignment.person))
    ).unique().scalars().all()

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
                    cell.assigned.append(CellPerson(
                        person_id=a.person_id, name=a.person.name, role=a.person.role,
                        slot=a.slot, position=a.position, severity=sev,
                    ))
                    if sev is not None and (worst is None or _SEVERITY_RANK[sev] < _SEVERITY_RANK[worst]):
                        worst = sev
                cell.worst_severity = worst
            cells[kind.value] = cell
        days.append(DayView(date=d, cells=cells))

    overlap_clause = and_(
        PresencePeriod.start_date <= end,
        PresencePeriod.end_date >= start,
    )
    rows = db.execute(
        select(Person)
        .join(PresencePeriod, PresencePeriod.person_id == Person.id)
        .where(Person.archived.is_(False))
        .where(overlap_clause)
        .order_by(Person.name)
        .distinct()
    ).scalars().all()

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
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_services_schedule.py -v`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/services.py tests/test_services_schedule.py
git commit -m "feat: schedule view-model service with severity tinting and sidebar chains"
```

---

## Task 22: Schedule route, templates, and sidebar partial

**Files:**
- Create: `src/shift_scheduler/routes/schedule.py`
- Create: `src/shift_scheduler/templates/schedule.html`
- Create: `src/shift_scheduler/templates/components/cell.html`
- Create: `src/shift_scheduler/templates/components/sidebar.html`
- Modify: `src/shift_scheduler/main.py` (replace placeholder include real router)
- Test: `tests/test_routes_schedule.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_routes_schedule.py`:

```python
from datetime import date

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def test_get_schedule_default_renders_14_days(client) -> None:
    r = client.get("/schedule")
    assert r.status_code == 200
    assert 'dir="rtl"' in r.text
    assert "morning" in r.text.lower() or "בוקר" in r.text


def test_get_schedule_with_explicit_range(client) -> None:
    r = client.get("/schedule?start=2026-06-01&end=2026-06-14")
    assert r.status_code == 200
    assert "2026-06-01" in r.text
    assert "2026-06-14" in r.text


def test_invalid_date_param_400(client) -> None:
    r = client.get("/schedule?start=not-a-date")
    assert r.status_code == 400


def test_inverted_range_400(client) -> None:
    r = client.get("/schedule?start=2026-06-10&end=2026-06-01")
    assert r.status_code == 400


def test_schedule_shows_logged_in_actions(client, settings) -> None:
    _login(client, settings)
    r = client.get("/schedule")
    assert "התנתק" in r.text
```

- [ ] **Step 2: Run tests — verify failure**

Run: `uv run pytest tests/test_routes_schedule.py -v`

Expected: FAIL — placeholder `/schedule` returns wrong markup.

- [ ] **Step 3: Write `src/shift_scheduler/routes/schedule.py`**

```python
from datetime import date as date_type, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from shift_scheduler.auth import (
    SESSION_COOKIE_NAME,
    SessionExpired,
    SessionInvalid,
    verify_session,
)
from shift_scheduler.config import Settings, get_settings
from shift_scheduler.db import get_db
from shift_scheduler.main import templates
from shift_scheduler.services import build_schedule_view
from shift_scheduler.shifts import TZ, ShiftKind

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
        verify_session(token, secret=settings.session_secret,
                       max_age_seconds=settings.session_max_age_seconds)
        return True
    except (SessionInvalid, SessionExpired):
        return False


@router.get("/schedule", response_class=HTMLResponse)
def schedule_page(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
        request, "schedule.html",
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
```

- [ ] **Step 4: Write `src/shift_scheduler/templates/schedule.html`**

```html
{% extends "base.html" %}
{% block content %}
<section class="schedule-toolbar">
  <a href="{{ prev_url }}">← אחורה</a>
  <strong>{{ view.start }} — {{ view.end }}</strong>
  <a href="{{ today_url }}">היום</a>
  <a href="{{ next_url }}">קדימה →</a>
</section>

<div class="layout" id="layout-root">
  <section class="schedule-grid" aria-label="לוח שיבוץ">
    <div class="col-header">תאריך</div>
    <div class="col-header">בוקר</div>
    <div class="col-header">צהריים</div>
    <div class="col-header">לילה</div>
    {% for day in view.days %}
      <div class="day-label">{{ day.date }}</div>
      {% for kind in ['morning', 'noon', 'night'] %}
        {% with cell = day.cells[kind] %}
          {% include "components/cell.html" %}
        {% endwith %}
      {% endfor %}
    {% endfor %}
  </section>
  {% include "components/sidebar.html" %}
</div>
{% endblock %}
```

- [ ] **Step 5: Write `src/shift_scheduler/templates/components/cell.html`**

```html
<div class="cell {% if cell.worst_severity %}tint-{{ cell.worst_severity.value }}{% endif %}"
     id="cell-{{ cell.date }}-{{ cell.kind.value }}"
     data-date="{{ cell.date }}" data-kind="{{ cell.kind.value }}">
  {% set commander_filled = false %}
  {% for person in cell.assigned if person.slot == 'commander' %}
    {% set commander_filled = true %}
    <div class="slot commander">
      {{ person.name }}
      {% if person.severity %}<span class="chip gap {{ person.severity.value }}">{{ person.severity.value }}</span>{% endif %}
      {% if edit_mode %}
        <form method="post" action="/shift/{{ cell.date }}/{{ cell.kind.value }}/unassign"
              hx-post="/shift/{{ cell.date }}/{{ cell.kind.value }}/unassign"
              hx-target="#cell-{{ cell.date }}-{{ cell.kind.value }}" hx-swap="outerHTML"
              class="inline">
          <input type="hidden" name="slot" value="commander">
          <input type="hidden" name="position" value="{{ person.position }}">
          <button type="submit" title="הסר">×</button>
        </form>
      {% endif %}
    </div>
  {% endfor %}
  {% if not commander_filled %}
    <div class="slot empty commander"
         {% if edit_mode %}data-pick-slot="commander" data-pick-position="0"{% endif %}>
      {% if edit_mode %}<button type="button" class="picker-trigger"
        data-date="{{ cell.date }}" data-kind="{{ cell.kind.value }}"
        data-slot="commander" data-position="0">➕ הוסף מפקד</button>
      {% else %}—{% endif %}
    </div>
  {% endif %}
  {% set operator_positions = range(0, cell.capacity['operator']) | list %}
  {% set filled_positions = cell.assigned | selectattr('slot','equalto','operator') | map(attribute='position') | list %}
  {% for op in cell.assigned if op.slot == 'operator' %}
    <div class="slot operator">
      {{ op.name }}
      {% if op.severity %}<span class="chip gap {{ op.severity.value }}">{{ op.severity.value }}</span>{% endif %}
      {% if edit_mode %}
        <form method="post" action="/shift/{{ cell.date }}/{{ cell.kind.value }}/unassign"
              hx-post="/shift/{{ cell.date }}/{{ cell.kind.value }}/unassign"
              hx-target="#cell-{{ cell.date }}-{{ cell.kind.value }}" hx-swap="outerHTML"
              class="inline">
          <input type="hidden" name="slot" value="operator">
          <input type="hidden" name="position" value="{{ op.position }}">
          <button type="submit" title="הסר">×</button>
        </form>
      {% endif %}
    </div>
  {% endfor %}
  {% for pos in operator_positions if pos not in filled_positions %}
    <div class="slot empty operator">
      {% if edit_mode %}<button type="button" class="picker-trigger"
        data-date="{{ cell.date }}" data-kind="{{ cell.kind.value }}"
        data-slot="operator" data-position="{{ pos }}">➕ הוסף מפעיל</button>
      {% else %}—{% endif %}
    </div>
  {% endfor %}
</div>
```

- [ ] **Step 6: Write `src/shift_scheduler/templates/components/sidebar.html`**

```html
<aside class="sidebar" id="rest-sidebar">
  <header>
    <strong>מנוחה</strong>
    <button type="button" class="toggle" id="sidebar-toggle" aria-label="כווץ">⇆</button>
  </header>
  <div class="body">
    {% for row in view.sidebar_rows %}
      <div class="person-row" id="sidebar-person-{{ row.person.id }}">
        <div><strong>{{ row.person.name }}</strong>
          <small>{{ "מפקד/ת" if row.person.role == "commander" else "מפעיל/ה" }}</small>
        </div>
        <div class="chips">
          {% for item in row.items %}
            {% if item.__class__.__name__ == 'ChainShift' %}
              <span class="chip shift">{{ item.date }} {{ item.kind.value }}</span>
            {% else %}
              <span class="chip gap {{ item.severity.value }}">{{ '%.1f'|format(item.hours) }}h</span>
            {% endif %}
          {% endfor %}
        </div>
      </div>
    {% else %}
      <p>אין אנשים בטווח התצוגה</p>
    {% endfor %}
  </div>
</aside>
```

- [ ] **Step 7: Wire the router and remove placeholder**

In `src/shift_scheduler/main.py`, **delete** the `@app.get("/schedule")` placeholder function and add **after** the `/` route:

```python
    from shift_scheduler.routes import schedule as schedule_routes
    app.include_router(schedule_routes.router)
```

- [ ] **Step 8: Run tests — verify pass**

Run: `uv run pytest tests/test_routes_schedule.py -v`

Expected: 5 passed.

- [ ] **Step 9: Commit**

```bash
git add src/shift_scheduler/routes/schedule.py \
        src/shift_scheduler/templates/schedule.html \
        src/shift_scheduler/templates/components/cell.html \
        src/shift_scheduler/templates/components/sidebar.html \
        src/shift_scheduler/main.py tests/test_routes_schedule.py
git commit -m "feat: schedule grid + rest sidebar with date-range navigation"
```

---

## Task 23: Sidebar JS (collapse with localStorage)

**Files:**
- Modify: `src/shift_scheduler/static/js/sidebar.js`
- Test: `tests/test_static_sidebar.py`

- [ ] **Step 1: Write the failing test**

`tests/test_static_sidebar.py`:

```python
from pathlib import Path


def test_sidebar_js_uses_local_storage_key() -> None:
    p = Path("src/shift_scheduler/static/js/sidebar.js")
    src = p.read_text(encoding="utf-8")
    assert "localStorage" in src
    assert "ss-sidebar-collapsed" in src
    assert "sidebar-toggle" in src
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_static_sidebar.py -v`

Expected: FAIL — placeholder file does not contain the expected tokens.

- [ ] **Step 3: Replace `src/shift_scheduler/static/js/sidebar.js`**

```javascript
(function () {
  const KEY = "ss-sidebar-collapsed";

  function applyState(collapsed) {
    const sidebar = document.getElementById("rest-sidebar");
    const layout = document.getElementById("layout-root");
    if (!sidebar || !layout) return;
    if (collapsed) {
      sidebar.classList.add("collapsed");
      layout.classList.add("sidebar-collapsed");
    } else {
      sidebar.classList.remove("collapsed");
      layout.classList.remove("sidebar-collapsed");
    }
  }

  function init() {
    const initial = localStorage.getItem(KEY) === "1";
    applyState(initial);
    const btn = document.getElementById("sidebar-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const next = !(localStorage.getItem(KEY) === "1");
      localStorage.setItem(KEY, next ? "1" : "0");
      applyState(next);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/test_static_sidebar.py -v`

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/static/js/sidebar.js tests/test_static_sidebar.py
git commit -m "feat: collapsible sidebar with localStorage persistence"
```

---

## Task 24: Picker — Alpine.js component + `GET /shift/{date}/{kind}/candidates`

**Files:**
- Modify: `src/shift_scheduler/routes/schedule.py` (append candidate endpoint)
- Create: `src/shift_scheduler/templates/components/picker.html`
- Modify: `src/shift_scheduler/templates/components/cell.html` (mount picker)
- Modify: `src/shift_scheduler/templates/schedule.html` (include picker partial)
- Test: `tests/test_routes_candidates.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_routes_candidates.py`:

```python
from datetime import date

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def _add(client, name: str, role: str, start: str, end: str) -> int:
    create = client.post("/roster", data={"name": name, "role": role}, follow_redirects=False)
    pid = int(create.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/roster/{pid}/periods", data={"start_date": start, "end_date": end})
    return pid


def test_candidates_requires_auth(client) -> None:
    r = client.get("/shift/2026-06-10/morning/candidates?slot=operator&position=0",
                   follow_redirects=False)
    assert r.status_code == 302


def test_candidates_filters_by_role_and_arrival(client, settings) -> None:
    _login(client, settings)
    op_id = _add(client, "מפעיל", "operator", "2026-06-09", "2026-06-15")
    cm_id = _add(client, "מפקד", "commander", "2026-06-09", "2026-06-15")
    _ = _add(client, "ארן", "operator", "2026-06-10", "2026-06-15")  # arrival day morning blocked

    r = client.get("/shift/2026-06-10/morning/candidates?slot=commander&position=0")
    assert r.status_code == 200
    assert "מפקד" in r.text
    assert "מפעיל" not in r.text  # operator can't fill commander slot
    assert "ארן" not in r.text     # arrival day morning blocked

    r = client.get("/shift/2026-06-10/morning/candidates?slot=operator&position=0")
    assert "מפעיל" in r.text
    assert "מפקד" in r.text   # commanders may fill operator slots
    assert "ארן" not in r.text


def test_candidates_typeahead_q(client, settings) -> None:
    _login(client, settings)
    _add(client, "אבי", "operator", "2026-06-01", "2026-06-30")
    _add(client, "בני", "operator", "2026-06-01", "2026-06-30")
    r = client.get("/shift/2026-06-10/noon/candidates?slot=operator&position=0&q=אב")
    assert "אבי" in r.text
    assert "בני" not in r.text
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_routes_candidates.py -v`

Expected: FAIL — `/shift/.../candidates` returns 404.

- [ ] **Step 3: Append candidates endpoint to `src/shift_scheduler/routes/schedule.py`**

```python
from sqlalchemy import select

from shift_scheduler.auth import require_editor
from shift_scheduler.models import Person, PresencePeriod
from shift_scheduler.services import _person_assignments_in_range
from shift_scheduler.shifts import (
    EligibilityResult,
    is_eligible,
    projected_worst_gap,
)


@router.get("/shift/{shift_date}/{kind}/candidates", response_class=HTMLResponse)
def candidates(
    shift_date: str,
    kind: str,
    request: Request,
    slot: str = Query(...),
    position: int = Query(0),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    _=require_editor(),
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
```

- [ ] **Step 4: Write `src/shift_scheduler/templates/components/picker.html`**

```html
<div class="picker" id="picker-pane"
     x-data="picker"
     @keydown.escape.window="open=false"
     @click.outside="open=false">
  <input type="search" name="q" placeholder="חיפוש שם…" x-model="query"
         hx-get="/shift/{{ shift_date }}/{{ kind }}/candidates"
         hx-trigger="keyup changed delay:200ms"
         hx-target="#picker-pane" hx-swap="outerHTML"
         hx-include="[name='slot'],[name='position']">
  <input type="hidden" name="slot" value="{{ slot }}">
  <input type="hidden" name="position" value="{{ position }}">
  {% for c in candidates %}
    <form method="post" action="/shift/{{ shift_date }}/{{ kind }}/assign"
          hx-post="/shift/{{ shift_date }}/{{ kind }}/assign"
          hx-target="#cell-{{ shift_date }}-{{ kind }}" hx-swap="outerHTML"
          class="candidate">
      <input type="hidden" name="slot" value="{{ slot }}">
      <input type="hidden" name="position" value="{{ position }}">
      <input type="hidden" name="person_id" value="{{ c.person.id }}">
      <button type="submit" class="candidate-btn">
        {{ c.person.name }}
        <small>{{ "מפקד/ת" if c.person.role == "commander" else "מפעיל/ה" }}</small>
        {% if c.severity %}
          <span class="chip gap {{ c.severity.value }} gap-projection">{{ c.severity.value }}</span>
        {% endif %}
      </button>
    </form>
  {% else %}
    <p>אין מועמדים מתאימים</p>
  {% endfor %}
</div>
```

- [ ] **Step 5: Append picker host to `src/shift_scheduler/templates/schedule.html`** — add **before** `{% endblock %}`:

```html
<div id="picker-host" hidden></div>
<script>
  document.addEventListener("click", function (ev) {
    const trigger = ev.target.closest(".picker-trigger");
    if (!trigger) return;
    ev.preventDefault();
    const { date, kind, slot, position } = trigger.dataset;
    const url = `/shift/${date}/${kind}/candidates?slot=${slot}&position=${position}`;
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        const host = document.getElementById("picker-host");
        host.innerHTML = html;
        host.hidden = false;
        const rect = trigger.getBoundingClientRect();
        const pane = document.getElementById("picker-pane");
        if (pane) {
          pane.style.position = "absolute";
          pane.style.top = (window.scrollY + rect.bottom + 4) + "px";
          pane.style.insetInlineStart = (rect.left + window.scrollX) + "px";
          if (window.htmx) { window.htmx.process(pane); }
        }
        document.addEventListener("click", function close(e) {
          if (!e.target.closest("#picker-pane") && !e.target.closest(".picker-trigger")) {
            host.hidden = true;
            host.innerHTML = "";
            document.removeEventListener("click", close);
          }
        });
        document.addEventListener("keydown", function esc(e) {
          if (e.key === "Escape") {
            host.hidden = true;
            host.innerHTML = "";
            document.removeEventListener("keydown", esc);
          }
        });
      });
  });
</script>
```

- [ ] **Step 6: Run — verify pass**

Run: `uv run pytest tests/test_routes_candidates.py -v`

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add src/shift_scheduler/routes/schedule.py \
        src/shift_scheduler/templates/components/picker.html \
        src/shift_scheduler/templates/schedule.html \
        tests/test_routes_candidates.py
git commit -m "feat: candidate picker endpoint + cell-mounted Alpine/HTMX popover"
```

---

## Task 25: Assignment write — `POST /shift/{date}/{kind}/assign`

**Files:**
- Modify: `src/shift_scheduler/routes/schedule.py` (append)
- Test: `tests/test_routes_assign.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_routes_assign.py`:

```python
from datetime import date

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def _add(client, name: str, role: str, start="2026-06-01", end="2026-06-30") -> int:
    r = client.post("/roster", data={"name": name, "role": role}, follow_redirects=False)
    pid = int(r.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/roster/{pid}/periods", data={"start_date": start, "end_date": end})
    return pid


def test_assign_requires_auth(client) -> None:
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "0", "person_id": "1"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login")


def test_assign_writes_row_and_returns_cell_html(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "0", "person_id": str(pid)})
    assert r.status_code == 200
    assert "id=\"cell-2026-06-10-noon\"" in r.text
    assert "דנה" in r.text
    assert "hx-swap-oob" in r.text  # OOB sidebar fragment


def test_assign_rejects_role_mismatch(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    r = client.post("/shift/2026-06-10/morning/assign",
                    data={"slot": "commander", "position": "0", "person_id": str(pid)})
    assert r.status_code == 400


def test_assign_rejects_arrival_morning(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "ארן", "operator", start="2026-06-10", end="2026-06-15")
    r = client.post("/shift/2026-06-10/morning/assign",
                    data={"slot": "operator", "position": "0", "person_id": str(pid)})
    assert r.status_code == 400


def test_assign_rejects_double_booking_same_shift(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    client.post("/shift/2026-06-10/noon/assign",
                data={"slot": "operator", "position": "0", "person_id": str(pid)})
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "1", "person_id": str(pid)})
    assert r.status_code == 400
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_routes_assign.py -v`

Expected: FAIL — `/shift/.../assign` returns 404.

- [ ] **Step 3: Append assign endpoint to `src/shift_scheduler/routes/schedule.py`**

Add `Shift` and `ShiftAssignment` to the existing `from shift_scheduler.models import …` line at the top of the file (Task 24 already brought in `Person, PresencePeriod`). `timedelta` and `select` are already imported in earlier tasks. Then append the route below.

The audit-log call is added in Task 27; this task focuses on assignment correctness and the OOB cell + sidebar response.

```python
from shift_scheduler.models import Shift, ShiftAssignment


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
    return body.replace('<aside class="sidebar"', '<aside class="sidebar" hx-swap-oob="outerHTML"', 1)


@router.post("/shift/{shift_date}/{kind}/assign", response_class=HTMLResponse)
def assign(
    shift_date: str,
    kind: str,
    request: Request,
    slot: str = Form(...),
    position: int = Form(...),
    person_id: int = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    _=require_editor(),
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
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/test_routes_assign.py -v`

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/routes/schedule.py tests/test_routes_assign.py
git commit -m "feat: POST /shift/{date}/{kind}/assign with OOB sidebar swap"
```

---

## Task 26: Unassign — `POST /shift/{date}/{kind}/unassign`

**Files:**
- Modify: `src/shift_scheduler/routes/schedule.py` (append)
- Test: `tests/test_routes_assign.py` (append)

- [ ] **Step 1: Append the failing tests**

```python
def test_unassign_removes_row_and_returns_cell(client, settings) -> None:
    _login(client, settings)
    pid = _add(client, "דנה", "operator")
    client.post("/shift/2026-06-10/noon/assign",
                data={"slot": "operator", "position": "0", "person_id": str(pid)})
    r = client.post("/shift/2026-06-10/noon/unassign",
                    data={"slot": "operator", "position": "0"})
    assert r.status_code == 200
    assert "id=\"cell-2026-06-10-noon\"" in r.text
    assert "דנה" not in r.text
    assert "hx-swap-oob" in r.text


def test_unassign_idempotent_when_empty(client, settings) -> None:
    _login(client, settings)
    r = client.post("/shift/2026-06-10/noon/unassign",
                    data={"slot": "operator", "position": "0"})
    assert r.status_code == 200
    assert "id=\"cell-2026-06-10-noon\"" in r.text


def test_unassign_requires_auth(client) -> None:
    r = client.post("/shift/2026-06-10/noon/unassign",
                    data={"slot": "operator", "position": "0"},
                    follow_redirects=False)
    assert r.status_code == 302
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_routes_assign.py -v`

Expected: FAIL — `/shift/.../unassign` returns 404.

- [ ] **Step 3: Append the unassign endpoint to `src/shift_scheduler/routes/schedule.py`**

```python
@router.post("/shift/{shift_date}/{kind}/unassign", response_class=HTMLResponse)
def unassign(
    shift_date: str,
    kind: str,
    request: Request,
    slot: str = Form(...),
    position: int = Form(...),
    db: Session = Depends(get_db),
    _=require_editor(),
):
    d = _parse_date(shift_date)
    try:
        kind_enum = ShiftKind(kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="kind") from e
    if slot not in ("commander", "operator"):
        raise HTTPException(status_code=400, detail="slot")

    shift = db.execute(
        select(Shift).where(Shift.date == d).where(Shift.kind == kind_enum.value)
    ).scalar_one_or_none()
    if shift is not None:
        a = db.execute(
            select(ShiftAssignment)
            .where(ShiftAssignment.shift_id == shift.id)
            .where(ShiftAssignment.slot == slot)
            .where(ShiftAssignment.position == position)
        ).scalar_one_or_none()
        if a is not None:
            db.delete(a)
            db.commit()

    span_start = d - timedelta(days=2)
    span_end = d + timedelta(days=14)
    view = build_schedule_view(db, start=span_start, end=span_end)
    cell_html = _render_cell(request, view, d, kind_enum, edit_mode=True)
    sidebar_html = _render_sidebar_oob(request, view)
    return HTMLResponse(content=cell_html + sidebar_html)
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/test_routes_assign.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/shift_scheduler/routes/schedule.py tests/test_routes_assign.py
git commit -m "feat: POST /shift/{date}/{kind}/unassign with OOB sidebar swap"
```

---

## Task 27: Audit log — `audit.py` + wire into every edit handler

**Files:**
- Create: `src/shift_scheduler/audit.py`
- Modify: `src/shift_scheduler/routes/schedule.py` (call `write_log` in assign + unassign)
- Modify: `src/shift_scheduler/routes/roster.py` (call `write_log` in create/update/archive + period CRUD)
- Modify: `src/shift_scheduler/routes/auth.py` (call `write_log` in successful login + logout)
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_audit.py`:

```python
import json

from sqlalchemy import select

from shift_scheduler.auth import SESSION_COOKIE_NAME, hash_password, sign_session
from shift_scheduler.config import Settings
from shift_scheduler.models import EditLog


def _login(client, settings: Settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    client.cookies.set(SESSION_COOKIE_NAME, token)


def _logs(engine_and_session) -> list[EditLog]:
    _, SessionLocal = engine_and_session
    with SessionLocal() as s:
        return list(s.execute(select(EditLog).order_by(EditLog.id)).scalars().all())


def test_create_person_writes_audit(client, settings, engine_and_session) -> None:
    _login(client, settings)
    client.post("/roster", data={"name": "דן", "role": "operator"})
    rows = _logs(engine_and_session)
    assert any(r.action == "person.create" for r in rows)


def test_assign_writes_audit_with_payload(client, settings, engine_and_session) -> None:
    _login(client, settings)
    create = client.post("/roster", data={"name": "דנה", "role": "operator"},
                         follow_redirects=False)
    pid = int(create.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/roster/{pid}/periods",
                data={"start_date": "2026-06-01", "end_date": "2026-06-30"})
    client.post("/shift/2026-06-10/noon/assign",
                data={"slot": "operator", "position": "0", "person_id": str(pid)})
    rows = _logs(engine_and_session)
    assign_rows = [r for r in rows if r.action == "assign.create"]
    assert assign_rows
    payload = json.loads(assign_rows[-1].payload_json)
    assert payload["person_id"] == pid
    assert payload["kind"] == "noon"
    assert payload["slot"] == "operator"


def test_login_success_writes_audit(client, settings, engine_and_session) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    client.post("/login", data={"password": "hunter2"})
    rows = _logs(engine_and_session)
    assert any(r.action == "auth.login" for r in rows)


def test_failed_login_does_not_write_audit(client, settings, engine_and_session) -> None:
    settings.admin_password_hash = hash_password("hunter2")
    client.post("/login", data={"password": "WRONG"})
    rows = _logs(engine_and_session)
    assert not any(r.action == "auth.login" for r in rows)
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_audit.py -v`

Expected: FAIL — no `audit` module / no audit rows written.

- [ ] **Step 3: Write `src/shift_scheduler/audit.py`**

```python
import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from shift_scheduler.auth import client_ip
from shift_scheduler.models import EditLog


def write_log(
    db: Session,
    *,
    request: Request,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> EditLog:
    row = EditLog(
        ip=client_ip(request),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
    )
    db.add(row)
    db.commit()
    return row
```

- [ ] **Step 4: Wire `write_log` into `routes/auth.py`**

Add at top:

```python
from shift_scheduler.audit import write_log
from shift_scheduler.db import get_db
from sqlalchemy.orm import Session
```

In `post_login`, after `rate_limiter.register_success(ip)` and before constructing the response, change the function signature to also depend on `db`, and write a log row:

```python
@router.post("/login")
def post_login(
    request: Request,
    password: str = Form(...),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    # ... existing rate-limit + verify checks above stay the same ...
    rate_limiter.register_success(ip)
    write_log(db, request=request, action="auth.login")
    token = sign_session("admin", secret=settings.session_secret,
                         max_age_seconds=settings.session_max_age_seconds)
    # ... existing cookie + redirect logic stays the same ...
```

In `post_logout`:

```python
@router.post("/logout")
def post_logout(request: Request, db: Session = Depends(get_db)):
    write_log(db, request=request, action="auth.logout")
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
```

- [ ] **Step 5: Wire `write_log` into `routes/roster.py`**

Add `from shift_scheduler.audit import write_log` at top.

In `roster_create`, after `db.commit()`:

```python
    write_log(db, request=request, action="person.create",
              entity_type="person", entity_id=person.id,
              payload={"name": person.name, "role": person.role})
```

In `person_update`, after `db.commit()`:

```python
    write_log(db, request=request, action="person.update",
              entity_type="person", entity_id=person.id,
              payload={"name": person.name, "role": person.role})
```

In `person_archive`, **change the signature** to accept `request: Request` and after `db.commit()`:

```python
    write_log(db, request=request, action="person.archive",
              entity_type="person", entity_id=person.id)
```

In `period_create`, after `db.commit()`:

```python
    write_log(db, request=request, action="period.create",
              entity_type="presence_period", entity_id=pp.id,
              payload={"person_id": person_id, "start_date": str(pp.start_date),
                       "end_date": str(pp.end_date), "note": pp.note})
```

In `period_update`, after `db.commit()`:

```python
    write_log(db, request=request, action="period.update",
              entity_type="presence_period", entity_id=pp.id,
              payload={"person_id": person_id, "start_date": str(pp.start_date),
                       "end_date": str(pp.end_date), "note": pp.note})
```

In `period_delete`, after `db.delete(pp)` and `db.commit()`:

```python
    write_log(db, request=request, action="period.delete",
              entity_type="presence_period", entity_id=period_id,
              payload={"person_id": person_id})
```

(All the period routes already accept `request` via the `_=require_editor()` plumbing — add `request: Request` to the function signature where missing.)

- [ ] **Step 6: Wire `write_log` into `routes/schedule.py`**

Add `from shift_scheduler.audit import write_log` at top.

In `assign`, after the final `db.commit()` and before `view = build_schedule_view(...)`:

```python
    write_log(db, request=request, action="assign.create",
              entity_type="shift_assignment", entity_id=a.id,
              payload={"shift_date": str(d), "kind": kind_enum.value,
                       "slot": slot, "position": position, "person_id": person_id})
```

In `unassign`, after the `db.commit()` inside the `if a is not None:` branch:

```python
        write_log(db, request=request, action="assign.delete",
                  entity_type="shift_assignment", entity_id=a.id,
                  payload={"shift_date": str(d), "kind": kind_enum.value,
                           "slot": slot, "position": position})
```

- [ ] **Step 7: Run — verify pass**

Run: `uv run pytest tests/test_audit.py -v`

Expected: 4 passed.

- [ ] **Step 8: Run full suite to confirm nothing else broke**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/shift_scheduler/audit.py \
        src/shift_scheduler/routes/auth.py \
        src/shift_scheduler/routes/roster.py \
        src/shift_scheduler/routes/schedule.py \
        tests/test_audit.py
git commit -m "feat: edit_log audit writes on every edit handler"
```

---

## Task 28: CLI — `python -m shift_scheduler.cli set-password`

**Files:**
- Create: `src/shift_scheduler/cli.py`
- Create: `src/shift_scheduler/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
from click.testing import CliRunner

from shift_scheduler.auth import verify_password
from shift_scheduler.cli import cli


def test_set_password_prompts_and_prints_env_line() -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["set-password"], input="hunter2\nhunter2\n")
    assert r.exit_code == 0
    out = r.output
    assert "ADMIN_PASSWORD_HASH=" in out
    line = next(line for line in out.splitlines() if line.startswith("ADMIN_PASSWORD_HASH="))
    h = line.split("=", 1)[1].strip()
    assert h.startswith("$argon2")
    assert verify_password(h, "hunter2") is True


def test_set_password_mismatch_exits_nonzero() -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["set-password"], input="aaa\nbbb\n")
    assert r.exit_code != 0
    assert "אינה תואמת" in r.output or "do not match" in r.output


def test_module_main_dispatches() -> None:
    import shift_scheduler.__main__ as m
    assert hasattr(m, "cli")
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_cli.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'shift_scheduler.cli'`.

- [ ] **Step 3: Write `src/shift_scheduler/cli.py`**

```python
import sys

import click

from shift_scheduler.auth import hash_password


@click.group()
def cli() -> None:
    """Shift Scheduler CLI."""


@cli.command("set-password")
@click.option("--password", default=None,
              help="Skip the prompt and use this value (CI use only).")
def set_password(password: str | None) -> None:
    """Hash a new admin password and print the env-var line to set."""
    if password is None:
        first = click.prompt("סיסמה חדשה", hide_input=True)
        confirm = click.prompt("אישור סיסמה", hide_input=True)
        if first != confirm:
            click.echo("הסיסמה אינה תואמת", err=True)
            sys.exit(2)
        password = first
    h = hash_password(password)
    click.echo("Add this line to your .env or systemd EnvironmentFile:")
    click.echo(f"ADMIN_PASSWORD_HASH={h}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Write `src/shift_scheduler/__main__.py`**

```python
from shift_scheduler.cli import cli

if __name__ == "__main__":
    cli()
```

- [ ] **Step 5: Run — verify pass**

Run: `uv run pytest tests/test_cli.py -v`

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/shift_scheduler/cli.py src/shift_scheduler/__main__.py tests/test_cli.py
git commit -m "feat: CLI set-password subcommand via click"
```

---

## Task 29: Deployment — systemd unit, INSTALL.md, README.md

**Files:**
- Create: `deploy/shift-scheduler.service`
- Create: `deploy/INSTALL.md`
- Create: `README.md`
- Test: `tests/test_deploy_files.py`

- [ ] **Step 1: Write the failing test**

`tests/test_deploy_files.py`:

```python
from pathlib import Path


def test_systemd_unit_has_required_directives() -> None:
    txt = Path("deploy/shift-scheduler.service").read_text(encoding="utf-8")
    assert "[Unit]" in txt
    assert "[Service]" in txt
    assert "[Install]" in txt
    assert "Restart=always" in txt
    assert "--port 2323" in txt
    assert "--host 127.0.0.1" in txt
    assert "--workers 1" in txt
    assert "EnvironmentFile=" in txt


def test_install_md_documents_steps() -> None:
    txt = Path("deploy/INSTALL.md").read_text(encoding="utf-8")
    for needle in ["set-password", "ADMIN_PASSWORD_HASH", "SESSION_SECRET",
                   "alembic upgrade head", "systemctl", "Cloudflare"]:
        assert needle in txt, f"Missing {needle!r} in INSTALL.md"


def test_readme_mentions_core_facts() -> None:
    txt = Path("README.md").read_text(encoding="utf-8")
    assert "shift" in txt.lower()
    assert "uv" in txt.lower()
    assert "2323" in txt
    assert "Hebrew" in txt or "RTL" in txt or "עברית" in txt
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/test_deploy_files.py -v`

Expected: FAIL — files do not exist.

- [ ] **Step 3: Write `deploy/shift-scheduler.service`**

```ini
[Unit]
Description=Shift Scheduler (FastAPI on port 2323)
After=network.target

[Service]
Type=simple
User=shifts
Group=shifts
WorkingDirectory=/opt/shift-scheduler
EnvironmentFile=/etc/shift-scheduler.env
ExecStart=/usr/local/bin/uv run uvicorn shift_scheduler.main:app --host 127.0.0.1 --port 2323 --workers 1
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Write `deploy/INSTALL.md`**

```markdown
# Shift Scheduler — Install on Linux home server

These steps assume Debian/Ubuntu, `uv` installed system-wide at `/usr/local/bin/uv`,
and Cloudflare already terminating HTTPS for the existing port-5055 app (we'll add a second hostname).

## 1. System user and directories

```bash
sudo useradd --system --create-home --home-dir /opt/shift-scheduler --shell /usr/sbin/nologin shifts
sudo mkdir -p /var/lib/shift-scheduler
sudo chown shifts:shifts /var/lib/shift-scheduler
sudo install -d -o shifts -g shifts /opt/shift-scheduler
```

## 2. Deploy code

```bash
sudo -u shifts git clone <repo-url> /opt/shift-scheduler
cd /opt/shift-scheduler
sudo -u shifts uv sync
```

## 3. Generate password hash and session secret

```bash
sudo -u shifts uv run python -m shift_scheduler.cli set-password
# copy the printed ADMIN_PASSWORD_HASH=... line

python3 -c "import secrets; print('SESSION_SECRET=' + secrets.token_urlsafe(48))"
```

## 4. Write `/etc/shift-scheduler.env`

```bash
sudo install -m 600 -o root -g shifts /dev/stdin /etc/shift-scheduler.env <<'EOF'
ADMIN_PASSWORD_HASH=<paste from previous step>
SESSION_SECRET=<paste from previous step>
DATABASE_URL=sqlite:////var/lib/shift-scheduler/data.db
COOKIE_SECURE=true
EOF
```

## 5. Apply schema

```bash
cd /opt/shift-scheduler
sudo -u shifts DATABASE_URL=sqlite:////var/lib/shift-scheduler/data.db \
  uv run alembic upgrade head
```

## 6. Install and enable systemd unit

```bash
sudo cp deploy/shift-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shift-scheduler
sudo systemctl status shift-scheduler
```

## 7. Cloudflare

Add a DNS record (or tunnel route) for `shifts.<your-domain>` pointing at this host on port 2323.
The app binds to 127.0.0.1, so use a Cloudflare Tunnel (preferred) or a local reverse-proxy
that exposes 2323 to the tunnel. TLS terminates at Cloudflare; the cookie's `Secure` flag
relies on that.

## 8. Backups

Add a nightly cron for `shifts`:

```cron
0 3 * * * sqlite3 /var/lib/shift-scheduler/data.db ".backup '/var/backups/shifts-$(date +\%F).db'" && find /var/backups -name 'shifts-*.db' -mtime +14 -delete
```

## 9. Update procedure

```bash
cd /opt/shift-scheduler
sudo -u shifts git pull
sudo -u shifts uv sync
sudo -u shifts DATABASE_URL=sqlite:////var/lib/shift-scheduler/data.db \
  uv run alembic upgrade head
sudo systemctl restart shift-scheduler
```
```

- [ ] **Step 5: Write `README.md`**

```markdown
# Shift Scheduler

Hebrew-RTL command-room shift scheduler for Miluim. Web app on port **2323**, behind Cloudflare HTTPS, on a home Linux server.

- **Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, SQLite, Jinja2, HTMX, Alpine.js, plain CSS.
- **Deps**: managed by `uv`. Lockfile committed.
- **Auth**: single shared password (argon2), signed-cookie sessions, in-memory rate limit.
- **No build step** — server-rendered HTML.

## Quickstart (dev)

```bash
uv sync --extra dev
cp .env.example .env
uv run python -m shift_scheduler.cli set-password
# paste the printed line into .env, generate SESSION_SECRET, then:
uv run alembic upgrade head
uv run uvicorn shift_scheduler.main:app --reload --port 2323
```

Open http://localhost:2323 — you should be redirected to `/schedule` (Hebrew RTL).

## Tests

```bash
uv run pytest
uv run ruff check
uv run mypy src
```

## Deployment

See `deploy/INSTALL.md` for the systemd-on-home-server setup and Cloudflare hookup.

## Spec

The product/architecture spec lives at `docs/superpowers/specs/2026-05-20-shift-scheduler-design.md`.
```

- [ ] **Step 6: Run — verify pass**

Run: `uv run pytest tests/test_deploy_files.py -v`

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add deploy/ README.md tests/test_deploy_files.py
git commit -m "docs: systemd unit, INSTALL.md, and README"
```

---

## Task 30: End-to-end smoke + final lint/type/test pass

**Files:**
- Create: `tests/test_e2e.py`
- Modify: any file flagged by ruff/mypy

- [ ] **Step 1: Write the E2E smoke test**

`tests/test_e2e.py`:

```python
import re

from shift_scheduler.auth import hash_password


def test_full_happy_path(client, settings) -> None:
    settings.admin_password_hash = hash_password("hunter2")

    # 1. Login
    r = client.post("/login", data={"password": "hunter2"}, follow_redirects=False)
    assert r.status_code == 302

    # 2. Add a person
    r = client.post("/roster", data={"name": "טליה", "role": "operator"},
                    follow_redirects=False)
    assert r.status_code == 302
    pid = int(r.headers["location"].rsplit("/", 1)[-1])

    # 3. Add a presence period
    r = client.post(f"/roster/{pid}/periods",
                    data={"start_date": "2026-06-01", "end_date": "2026-06-30"},
                    follow_redirects=False)
    assert r.status_code == 302

    # 4. Assign to a shift
    r = client.post("/shift/2026-06-10/noon/assign",
                    data={"slot": "operator", "position": "0", "person_id": str(pid)})
    assert r.status_code == 200

    # 5. Verify schedule renders the assignment
    page = client.get("/schedule?start=2026-06-01&end=2026-06-14")
    assert page.status_code == 200
    assert "טליה" in page.text

    # 6. Verify sidebar lists the person and shows at least one shift chip
    assert "sidebar-person-" in page.text
    assert re.search(r"chip\s+shift", page.text)
```

- [ ] **Step 2: Run E2E — verify pass**

Run: `uv run pytest tests/test_e2e.py -v`

Expected: 1 passed.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -q`

Expected: all tests pass (target: 70+).

- [ ] **Step 4: Run ruff**

Run: `uv run ruff check`

Expected: no errors. If any: fix in place (no `noqa` blanket suppressions).

- [ ] **Step 5: Run mypy**

Run: `uv run mypy src`

Expected: `Success: no issues found`. If any: add explicit annotations or refine types until clean. Don't add `# type: ignore` without a comment explaining why.

- [ ] **Step 6: Format**

Run: `uv run ruff format`

Expected: zero diffs after running twice (idempotent).

- [ ] **Step 7: Commit**

```bash
git add tests/test_e2e.py
git add -u  # any formatter/lint fixes
git commit -m "test: E2E smoke (login → person → period → assign → sidebar) and clean lint/types"
```

---

## Done — verification checklist

When all 30 tasks are complete, run and confirm:

- [ ] `uv run pytest -q` — all green
- [ ] `uv run ruff check` — clean
- [ ] `uv run mypy src` — clean
- [ ] `uv run uvicorn shift_scheduler.main:app --port 2323` — starts and serves `/schedule`
- [ ] Manual check (Hebrew RTL): `<html dir="rtl" lang="he">` is in the rendered HTML
- [ ] Manual check: 14 days × 3 shift columns visible at `/schedule`
- [ ] Manual check: clicking an empty slot in edit mode opens the picker; selecting a candidate populates the cell and updates the sidebar
- [ ] Manual check: ESC and outside-click both close the picker
- [ ] Manual check: collapse/expand sidebar persists across reloads
- [ ] `cat /var/lib/shift-scheduler/data.db` row counts grow only via the editor flow; `edit_log` has rows for every edit
