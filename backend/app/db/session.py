from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_config


def make_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    is_sqlite = url.get_backend_name() == "sqlite"
    sqlite_database = url.database if is_sqlite else None
    is_memory_database = (
        sqlite_database in (None, "", ":memory:")
        or (
            sqlite_database.startswith("file:")
            and url.query.get("mode") == "memory"
        )
    ) if is_sqlite else False

    if is_sqlite and not is_memory_database and sqlite_database is not None:
        Path(sqlite_database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 5} if is_sqlite else {},
        future=True,
    )

    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=5000")
                if not is_memory_database:
                    cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    return engine


engine = make_engine(get_config().resolved_database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
