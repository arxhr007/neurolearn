"""SQLAlchemy engine and session helpers."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


logger = logging.getLogger(__name__)

settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)


@event.listens_for(engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Make SQLite usable under concurrent requests.

    In the default `delete` journal mode a writer blocks every reader, and
    concurrent writers fail outright with "database is locked". Tutor requests
    hold their session across a multi-second LLM call before committing, so two
    students finishing a turn at once is enough to collide.

    WAL lets readers proceed during a write; busy_timeout makes a blocked writer
    wait instead of failing immediately. journal_mode persists in the file, the
    rest are per-connection.
    """
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        # Safe to relax with WAL: a crash can lose the last commits but cannot
        # corrupt the database.
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
    except Exception:
        logger.warning("Could not apply SQLite pragmas", exc_info=True)
    finally:
        cursor.close()


def _ensure_sqlite_parent_dir() -> None:
    """Create the directory holding the SQLite file if it is missing.

    SQLite will create the database file but not its parent directory, so a
    fresh checkout otherwise dies at startup with
    `sqlite3.OperationalError: unable to open database file`.
    """
    if engine.dialect.name != "sqlite":
        return
    db_path = engine.url.database
    if not db_path or db_path == ":memory:":
        return
    Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    _ensure_sqlite_parent_dir()
    Base.metadata.create_all(bind=engine)

    _migrate_schema()


def _migrate_schema() -> None:
    """Add new columns to existing tables if they don't exist."""
    import logging
    logger = logging.getLogger(__name__)
    with engine.connect() as conn:
        if engine.dialect.name != "sqlite":
            return
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(students)")).fetchall()
        }
        additions = {
            "father_name": "VARCHAR(120)",
            "mother_name": "VARCHAR(120)",
            "grandfather_name": "VARCHAR(120)",
            "grandmother_name": "VARCHAR(120)",
            "favorite_color": "VARCHAR(60)",
            "teacher_name": "VARCHAR(120)",
            "place": "VARCHAR(200)",
            "friends": "VARCHAR(500)",
            "favorite_food": "VARCHAR(120)",
            "favorite_animal": "VARCHAR(120)",
            "favorite_interest": "VARCHAR(120)",
        }
        for col, col_type in additions.items():
            if col not in existing:
                sql = text(f"ALTER TABLE students ADD COLUMN {col} {col_type}")
                conn.execute(sql)
                logger.info("Added column students.%s", col)
        conn.commit()
