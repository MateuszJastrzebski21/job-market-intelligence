"""FastAPI dependency providers.

Each function here is overridable in tests via ``app.dependency_overrides[...]``.
The repository dependency wraps the existing ``get_session`` context manager so
the session opens and closes around a single request lifecycle.
"""

from collections.abc import Iterator

import structlog
from sqlalchemy import text

from jmi.config import Settings, get_settings
from jmi.db.base import get_session
from jmi.storage.jobs import JobPostingRepository

log = structlog.get_logger(__name__)


def get_app_settings() -> Settings:
    """Settings provider — single call site so tests can override cleanly."""
    return get_settings()


def get_posting_repo() -> Iterator[JobPostingRepository]:
    """Yield a JobPostingRepository bound to a fresh DB session.

    Session is committed on clean handler exit, rolled back on exception.
    """
    with get_session() as session:
        yield JobPostingRepository(session)


def health_db_check() -> bool:
    """True if SELECT 1 succeeds against the configured database."""
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.warning("health.db.fail", error=str(exc))
        return False
