"""SQLAlchemy engine and session helpers."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
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
