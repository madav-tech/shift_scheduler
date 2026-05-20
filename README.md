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
