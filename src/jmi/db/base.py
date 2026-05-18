from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from jmi.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    return create_engine(url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide Engine, created lazily on first call.

    Lazy + cached: importing this module no longer opens a connection pool or
    reads settings as an import-time side effect (#23)."""
    return _make_engine()


def _get_session_local() -> sessionmaker[Session]:
    """A sessionmaker bound to the lazily-created engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False, class_=Session)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session: commit on clean exit, rollback on error."""
    session = _get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
