"""Repository for ``tailored_resumes`` audit-trail rows (PR-3.4).

A thin domain ↔ ORM boundary mirroring ``AchievementRepository``: callers hand
Pydantic ``TailoredResumeRow`` instances; SQLAlchemy stays behind the session.

This row type is the *storage* shape — orchestrating code constructs it from
the richer ``TailoredResume`` Pydantic model (lands in PR-3.4c) before
persisting. Keeping the storage shape minimal lets the rich domain schemas
evolve without churning the persistence layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jmi.db.models import TailoredResumeORM


class TailoredResumeRow(BaseModel):
    """One row of ``tailored_resumes`` as a typed domain value."""

    model_config = ConfigDict(extra="forbid", frozen=False, arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    jd_hash: str = Field(min_length=64, max_length=64)
    jd_text: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    company_domain: str | None = None
    role_title: str | None = None
    bullets_json: list[dict[str, Any]]
    cover_letter: str
    cover_letter_meta: dict[str, Any]
    research_blob: dict[str, Any] | None = None
    chunk_ids_used: list[str]
    cost_usd: float = Field(ge=0)
    total_tokens: int = Field(ge=0)
    web_search_calls: int = Field(ge=0, default=0)
    generation_duration_ms: int = Field(ge=0)
    model_versions: dict[str, str]


class TailoredResumeRepository:
    """Reads and writes ``tailored_resumes`` rows.

    Write is append-only — each generation is a distinct audit-trail entry.
    There is no upsert path; the same JD generated twice produces two rows
    (the operator can spot duplicates via ``find_by_jd_hash``).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, row: TailoredResumeRow) -> UUID:
        """Insert ``row`` and return its UUID. Caller commits the surrounding session."""
        orm = _row_to_orm(row)
        self._session.add(orm)
        self._session.flush()
        return orm.id

    def get(self, id: UUID) -> TailoredResumeRow | None:
        orm = self._session.get(TailoredResumeORM, id)
        return _orm_to_row(orm) if orm else None

    def find_by_jd_hash(self, jd_hash: str) -> list[TailoredResumeRow]:
        """All rows matching ``jd_hash``, newest first."""
        stmt = (
            select(TailoredResumeORM)
            .where(TailoredResumeORM.jd_hash == jd_hash)
            .order_by(TailoredResumeORM.created_at.desc())
        )
        return [_orm_to_row(o) for o in self._session.execute(stmt).scalars()]

    def count(self) -> int:
        from sqlalchemy import func

        return int(self._session.scalar(select(func.count(TailoredResumeORM.id))) or 0)


def _row_to_orm(row: TailoredResumeRow) -> TailoredResumeORM:
    return TailoredResumeORM(
        id=row.id,
        created_at=row.created_at,
        jd_hash=row.jd_hash,
        jd_text=row.jd_text,
        company_name=row.company_name,
        company_domain=row.company_domain,
        role_title=row.role_title,
        bullets_json=row.bullets_json,
        cover_letter=row.cover_letter,
        cover_letter_meta=row.cover_letter_meta,
        research_blob=row.research_blob,
        chunk_ids_used=list(row.chunk_ids_used),
        cost_usd=Decimal(str(row.cost_usd)),
        total_tokens=row.total_tokens,
        web_search_calls=row.web_search_calls,
        generation_duration_ms=row.generation_duration_ms,
        model_versions=row.model_versions,
    )


def _orm_to_row(o: TailoredResumeORM) -> TailoredResumeRow:
    return TailoredResumeRow(
        id=o.id,
        created_at=o.created_at,
        jd_hash=o.jd_hash,
        jd_text=o.jd_text,
        company_name=o.company_name,
        company_domain=o.company_domain,
        role_title=o.role_title,
        bullets_json=list(o.bullets_json),
        cover_letter=o.cover_letter,
        cover_letter_meta=dict(o.cover_letter_meta),
        research_blob=dict(o.research_blob) if o.research_blob is not None else None,
        chunk_ids_used=list(o.chunk_ids_used),
        cost_usd=float(o.cost_usd),
        total_tokens=o.total_tokens,
        web_search_calls=o.web_search_calls,
        generation_duration_ms=o.generation_duration_ms,
        model_versions=dict(o.model_versions),
    )
