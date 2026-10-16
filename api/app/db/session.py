"""SQLAlchemy engine and session (SQLite WAL)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_data_dir() -> None:
    settings.labledger_data_dir.mkdir(parents=True, exist_ok=True)
    (settings.labledger_data_dir / "files").mkdir(parents=True, exist_ok=True)
    (settings.labledger_data_dir / "backups").mkdir(parents=True, exist_ok=True)


def _attach_sqlite_pragmas(eng: Engine) -> None:
    @event.listens_for(eng, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


_ensure_data_dir()

engine: Engine = create_engine(
    settings.sqlalchemy_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
_attach_sqlite_pragmas(engine)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def configure_engine(url: str | None = None) -> Engine:
    """Rebuild engine/session (used by tests with a temp DB)."""
    global engine, SessionLocal
    _ensure_data_dir()
    engine = create_engine(
        url or settings.sqlalchemy_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    _attach_sqlite_pragmas(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    return engine


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if needed (prefer Alembic migrate in normal flow)."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()
