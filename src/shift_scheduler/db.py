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
