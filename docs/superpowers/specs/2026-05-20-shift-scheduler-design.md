# Shift Scheduler — Design

**Status**: Approved (brainstorm phase)
**Date**: 2026-05-20
**Owner**: Madav
**Deployment target**: Home server (Dell laptop, Linux), exposed via Cloudflare like the existing port-5055 app.

## 1. Purpose

A web app for managing command-room shifts during Miluim. The people in charge of the schedule arrange shifts manually for now (a future iteration may add an automated optimizer). The app must make rest patterns between shifts visible at a glance, validate eligibility, and run unattended in the background on a home server.

## 2. Domain rules

### 2.1 Shifts

Three shifts per day in Asia/Jerusalem time:

| Shift   | Start | End   | Crew (Commanders + Operators)             |
|---------|-------|-------|-------------------------------------------|
| Morning | 06:00 | 14:00 | 1 commander + 2 operators                 |
| Noon    | 14:00 | 22:00 | 1 commander + 2 operators                 |
| Night   | 22:00 | 06:00 (next day) | 1 commander + 1 operator       |

### 2.2 Roles

- Two roles: **commander** and **operator**.
- A **commander slot** can only be filled by a person whose `role = commander`.
- An **operator slot** can be filled by anyone (commanders may fulfil operator slots, but operators may not fulfil commander slots).
- A person's role can be edited at any time. Historical assignments record the slot they filled (commander or operator), so the past stays correct even if the role is later changed.

### 2.3 Availability — on-base periods

A person has zero or more **on-base periods**. Each period is a `(start_date, end_date)` inclusive range.

- The **first day** of a period is the arrival day. On that day, the person is **not eligible** for the morning shift (because they arrive during the day), but **is eligible** for noon and night.
- All other days in the period (including the last day) are fully eligible for all three shifts. (The last day "they're leaving the day after", so the night shift that ends 06:00 the next day is still fine.)
- A person can have multiple non-contiguous periods (e.g. leave for a few days, come back).

### 2.4 Rest rules

For a person with consecutive assigned shifts, the **rest gap** is the hours from the end of the earlier shift to the start of the later one.

| Gap (hours) | Severity   | Visual                         |
|-------------|------------|--------------------------------|
| `< 8`       | critical   | red chip + red cell highlight  |
| `== 8`      | warning    | yellow chip + yellow cell tint |
| `> 8`       | ok         | green chip, no cell highlight  |

**Nothing is hard-forbidden.** The editor sees the warning but can still assign. A cell's highlight is the worst severity among the people assigned to it.

### 2.5 Schedule shape

- **Rolling timeline**: one continuous calendar, no week/tour boundaries. Shift rows in the database are **lazily created** on first assignment to a slot (no scheduled backfill, no schedule object).
- Default visible range on `/schedule`: **today + 13 forward days** (14 days total). Navigable forward and backward.

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Browser (Hebrew RTL, desktop-first)           │
│   Jinja2-rendered HTML + HTMX swaps + Alpine.js bits    │
└─────────────────────────────────────────────────────────┘
                        │ HTTP
                        ▼
┌─────────────────────────────────────────────────────────┐
│             FastAPI (Python, single process)            │
│   ├── Public read routes                                │
│   ├── Edit routes (session-gated)                       │
│   ├── Cookie session auth, single shared password       │
│   └── Jinja2 + Tailwind CSS                             │
└─────────────────────────────────────────────────────────┘
                        │ SQLAlchemy
                        ▼
┌─────────────────────────────────────────────────────────┐
│   SQLite file on home server                            │
└─────────────────────────────────────────────────────────┘
                        │
              systemd unit, restart=always
                        │
                 Cloudflare (DNS / Tunnel)
              → shifts.<your-domain> (HTTPS)
```

- **Single process**, managed by systemd. Listens on **port 5056** locally.
- **Cloudflare** terminates TLS at the edge, like the existing port-5055 app.
- **Static assets** (Tailwind, HTMX, Alpine.js) bundled into the repo — no CDN required.
- **No build step** — server-rendered HTML with HTMX/Alpine for interactivity.

## 4. Data model

```sql
person (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  role       TEXT NOT NULL CHECK(role IN ('commander','operator')),
  archived   BOOLEAN NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL
);

presence_period (
  id         INTEGER PRIMARY KEY,
  person_id  INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  start_date DATE NOT NULL,
  end_date   DATE NOT NULL,
  note       TEXT,
  CHECK (end_date >= start_date)
);

shift (
  id   INTEGER PRIMARY KEY,
  date DATE NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('morning','noon','night')),
  UNIQUE(date, kind)
);

shift_assignment (
  id         INTEGER PRIMARY KEY,
  shift_id   INTEGER NOT NULL REFERENCES shift(id) ON DELETE CASCADE,
  person_id  INTEGER NOT NULL REFERENCES person(id),
  slot       TEXT NOT NULL CHECK(slot IN ('commander','operator')),
  position   INTEGER NOT NULL,
  note       TEXT,
  created_at TIMESTAMP NOT NULL,
  UNIQUE(shift_id, slot, position),
  UNIQUE(shift_id, person_id)
);

edit_log (
  id          INTEGER PRIMARY KEY,
  ts          TIMESTAMP NOT NULL,
  ip          TEXT,
  action      TEXT NOT NULL,
  entity_type TEXT,
  entity_id   INTEGER,
  payload_json TEXT
);
```

### Application-enforced invariants

- Per shift: 1 commander slot (`slot='commander', position=0`) + 2 operator slots for morning/noon, 1 operator slot for night.
- A person may not appear twice in the same shift (`UNIQUE(shift_id, person_id)`).
- Assignment eligibility checked at assign time (not enforced by DB):
  1. Person not archived.
  2. Person has a presence_period covering the shift's date.
  3. Not arrival-day-morning rule violation.
  4. Role-slot compatibility (commander slot ↔ commander only).

## 5. Pages & UX

### 5.1 Routes

| Method | Path                              | Auth     | Purpose                                  |
|--------|-----------------------------------|----------|------------------------------------------|
| GET    | `/`                               | public   | Redirect to `/schedule`                  |
| GET    | `/schedule`                       | public   | Main schedule view (14-day default)      |
| GET    | `/roster`                         | public (read), edit (write) | People list             |
| GET    | `/roster/{id}`                    | public (read), edit (write) | Person detail + periods |
| POST   | `/roster`                         | edit     | Create person                            |
| POST   | `/roster/{id}`                    | edit     | Update person                            |
| POST   | `/roster/{id}/archive`            | edit     | Archive (soft delete)                    |
| POST   | `/roster/{id}/periods`            | edit     | Create presence period                   |
| POST   | `/roster/{id}/periods/{pid}`      | edit     | Update presence period                   |
| POST   | `/roster/{id}/periods/{pid}/delete` | edit   | Delete presence period                   |
| POST   | `/shift/{date}/{kind}/assign`     | edit     | Assign person to slot. Form body: `slot` ∈ {commander, operator}, `position` (int), `person_id`, optional `note`. Returns the updated cell HTML + an HTMX OOB swap for the sidebar |
| POST   | `/shift/{date}/{kind}/unassign`   | edit     | Remove person from slot. Form body: `slot`, `position`. Returns updated cell + OOB sidebar |
| GET    | `/login`                          | public   | Login form                               |
| POST   | `/login`                          | public   | Verify password, set session             |
| POST   | `/logout`                         | edit     | Clear session                            |

### 5.2 `/schedule` page

- **Layout**: day rows × shift columns (Layout A). 4 columns: date | morning | noon | night. RTL.
- **Header**: prev range button, current date range label, "today" button, next range button, link to roster, login/logout link.
- **Cells**:
  - Show commander on top (with ★), operators below.
  - Cell is tinted using the **worst severity** among the people assigned to it: red if any person has a `<8h` gap on either side of this shift, yellow if any person has a `==8h` gap, otherwise no tint.
  - Empty slots: in view mode show dash; in edit mode show "➕ הוסף" placeholder.
- **Rest sidebar** (right side, collapsible):
  - Header with collapse button. Collapsed state persisted to `localStorage`.
  - Lists every non-archived person with a presence period overlapping the visible range.
  - Each row: name + role marker + colored chips for shifts and rest gaps.
  - Updates live via HTMX out-of-band swaps after any assignment change.

### 5.3 Assignment picker (Alpine.js inline popover)

Triggered by clicking a cell slot in edit mode. The clicked DOM element carries `data-date`, `data-kind`, `data-slot`, `data-position` so the picker knows which slot to populate.

- Typeahead input at top.
- List of eligible candidates filtered by role + availability + arrival rule.
- Next to each candidate: their **projected rest gap** if assigned ("8h ⚠", "24h", etc.).
- Click a name → submits `POST /shift/{date}/{kind}/assign` with form body `slot`, `position`, `person_id` → cell + sidebar update via HTMX.
- ESC closes; clicking outside closes.

### 5.4 Roster pages

- `/roster`: table of people (name, role, current/upcoming presence summary). "Add person" button.
- `/roster/{id}`: form for name + role + archive button; below, list of presence periods with add/edit/delete buttons.

## 6. Rest calculation algorithm

For each person rendered in the sidebar:

1. Fetch their assignments where `shift.date` is within `[visible_start - 1, visible_end + 1]` (extended by one day on each side so edge chains are computed against immediately adjacent shifts when they exist).
2. Convert each to `(start_dt, end_dt)` in `Asia/Jerusalem` (using `zoneinfo`; DST-correct).
3. Sort by `start_dt`.
4. Walk consecutive pairs and compute `gap_hours = (next.start_dt - prev.end_dt).total_seconds() / 3600`.
5. Produce an interleaved sequence `[shift_chip, gap_chip, shift_chip, gap_chip, ...]`. Classify each gap by the table in §2.4.

For the picker's "projected gap":

- Find the person's previous assignment ending before the candidate shift's start.
- Find the person's next assignment starting after the candidate shift's end.
- Compute both gaps; show the worse severity (smaller hours wins for severity).
- If neither neighbour exists, show "no nearby shifts" or just omit the gap chip.

## 7. Authentication & security

- **Single shared password**. Hashed with **argon2** (`argon2-cffi`) and stored in env var `ADMIN_PASSWORD_HASH`.
- CLI command `python -m shift_scheduler.cli set-password` prompts, hashes, and prints the env-var line.
- **Session cookie**: signed (HMAC) with `SESSION_SECRET` env var. Cookie flags: `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`. Expiry: 12 hours.
- **Rate limiting**: 5 failed logins in 15 min per IP → 15-min lockout. In-memory dict keyed by `CF-Connecting-IP` (falling back to remote addr). Resets on process restart.
- **CSRF**: relying on `SameSite=Lax` for now. (Decision: no extra tokens in v1.)
- **Audit log**: every successful edit writes a row to `edit_log` with timestamp, IP, action, entity, payload.

## 8. Deployment

### 8.1 Repository layout

```
shift_scheduler/
├── pyproject.toml
├── README.md
├── .env.example
├── alembic.ini
├── migrations/versions/
├── src/shift_scheduler/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── shifts.py
│   ├── routes/{schedule.py, roster.py, auth.py}
│   ├── templates/{base.html, schedule.html, roster.html, person.html, login.html, components/…}
│   ├── static/{css/, js/}
│   └── cli.py
├── tests/{conftest.py, test_shifts.py, test_routes_*.py, test_auth.py}
└── deploy/{shift-scheduler.service, INSTALL.md}
```

### 8.2 Tooling

- **`uv`** for dependency management. Lock file committed.
- **Alembic** for schema migrations.
- **`ruff`** for lint + format. Pre-commit hook.
- **`mypy`** for type checking.

### 8.3 Run

- **Dev**: `uv run uvicorn shift_scheduler.main:app --reload --port 5056`
- **Prod**: systemd unit running `uv run uvicorn shift_scheduler.main:app --host 127.0.0.1 --port 5056 --workers 1`

### 8.4 Backups

- Nightly cron: `sqlite3 data.db ".backup '/backups/shifts-$(date +%F).db'"`. Retain last 14.

## 9. Testing strategy

- **Unit tests** for pure logic: shift time arithmetic, eligibility predicate, rest-chain calculation, severity classification. No DB.
- **Integration tests** for routes using `TestClient` + in-memory SQLite.
- **One end-to-end smoke test**: login → add person → add presence period → assign to shift → verify sidebar updates.
- **CI**: deferred — pre-commit + manual `uv run pytest` is enough for v1.

## 10. Out of scope for v1

- Automated assignment algorithm (manual only for v1).
- Multi-user accounts / per-person logins.
- Import/export (CSV, ICS).
- Notifications (email, push).
- Mobile-optimized layout (works on mobile but not tuned).
- Cloudflare Access integration (you can layer it on independently if desired).
- Internationalization toggle (Hebrew RTL only).
- Print-friendly view.
