from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from jmi.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    return create_engine(url, future=True, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session: commit on clean exit, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
