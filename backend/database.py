"""SQLAlchemy setup and DB session management."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.config import DATABASE_URL, SQLITE_PATH

if DATABASE_URL.startswith("sqlite:///"):
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so SQLAlchemy can discover table metadata before create_all.
    from backend.auth import models as auth_models  # noqa: F401
    from backend.chat import models as chat_models  # noqa: F401
    from backend.movies import models as movie_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from backend.chat.migrate import run_migrations

    run_migrations()
