"""Database setup for backend services."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass

settings = get_settings()

# Ensure SQLite database directory exists if using a file-based SQLite URL
if settings.database_url.startswith("sqlite:///"):
    db_path_str = settings.database_url.replace("sqlite:///", "", 1)
    db_path = Path(db_path_str)
    if db_path.parent and not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)


if settings.database_url.startswith("sqlite://"):
    # SQLite: allow use from multiple threads and increase timeout to reduce
    # 'database is locked' errors under concurrent access
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
