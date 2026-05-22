"""Repository for ``company_research_cache`` rows (PR-3.4).

7-day TTL by default; enforced application-side. Saves the ~$0.078
research-call cost on repeat applications to the same company within the
window. Bypass via the ``--refresh-research`` CLI flag (planned PR-3.4d) or by
calling ``put()`` with a fresh ``fetched_at``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from jmi.db.models import CompanyResearchCacheORM

CACHE_TTL_DAYS: int = 7


class CompanyResearchCacheRow(BaseModel):
    """One cached company research blob, keyed by SHA256(name + '|' + domain)."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    key: str = Field(min_length=64, max_length=64)
    company_name: str = Field(min_length=1)
    company_domain: str | None = None
    research_json: dict[str, Any]
    fetched_at: datetime


class CompanyResearchCacheRepository:
    """Read/write/purge cached company research blobs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def make_key(company_name: str, company_domain: str | None) -> str:
        """SHA256 of normalised ``company_name + '|' + (domain or '')``.

        Normalisation: strip + lower. Keeps "Acme Corp" / " acme corp " /
        "ACME CORP" colliding into the same cache entry.
        """
        payload = f"{company_name.strip().lower()}|{(company_domain or '').strip().lower()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str, *, ttl_days: int = CACHE_TTL_DAYS) -> CompanyResearchCacheRow | None:
        """Return the cached row if it exists and is within ``ttl_days`` of now."""
        orm = self._session.get(CompanyResearchCacheORM, key)
        if orm is None:
            return None
        age = datetime.now(UTC).replace(tzinfo=None) - orm.fetched_at
        if age > timedelta(days=ttl_days):
            return None
        return _orm_to_row(orm)

    def put(self, row: CompanyResearchCacheRow) -> None:
        """Insert ``row`` or overwrite the existing row with the same ``key``.

        Caller commits the surrounding session.
        """
        existing = self._session.get(CompanyResearchCacheORM, row.key)
        if existing is None:
            self._session.add(_row_to_orm(row))
        else:
            existing.company_name = row.company_name
            existing.company_domain = row.company_domain
            existing.research_json = row.research_json
            existing.fetched_at = row.fetched_at
        self._session.flush()

    def purge_expired(self, *, ttl_days: int = CACHE_TTL_DAYS) -> int:
        """Delete rows whose ``fetched_at`` is older than ``ttl_days``. Returns count."""
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=ttl_days)
        # Session.execute() returns Result[Any] in the typestubs but a DML DELETE
        # at runtime is a CursorResult; cast to read .rowcount type-safely.
        result = cast(
            "CursorResult[Any]",
            self._session.execute(
                delete(CompanyResearchCacheORM).where(CompanyResearchCacheORM.fetched_at < cutoff)
            ),
        )
        self._session.flush()
        return result.rowcount or 0


def _row_to_orm(row: CompanyResearchCacheRow) -> CompanyResearchCacheORM:
    return CompanyResearchCacheORM(
        key=row.key,
        company_name=row.company_name,
        company_domain=row.company_domain,
        research_json=row.research_json,
        fetched_at=row.fetched_at,
    )


def _orm_to_row(o: CompanyResearchCacheORM) -> CompanyResearchCacheRow:
    return CompanyResearchCacheRow(
        key=o.key,
        company_name=o.company_name,
        company_domain=o.company_domain,
        research_json=dict(o.research_json),
        fetched_at=o.fetched_at,
    )
