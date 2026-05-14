"""Tests for the nullable description columns introduced by PR2 (Alembic 0002).

Scope: Pydantic-model contract + the in-process domain ↔ ORM mapper round trip.
A DB-backed repository integration test is deferred to a follow-up PR that
introduces testcontainers (or equivalent) — see PR2 description. Schema-level
correctness for this migration is otherwise covered by:
  - the Alembic offline dry-run (`alembic upgrade --sql head`) verified during
    PR2 development
  - the live `alembic upgrade head` against the dev database, with
    `information_schema.columns.is_nullable` returning YES afterward.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from jmi.db.models import JobPostingORM
from jmi.models.job import JobPosting
from jmi.storage.jobs import _posting_to_domain, _posting_to_orm


def _make_posting(**overrides: object) -> JobPosting:
    defaults: dict[str, object] = {
        "source": "huggingface",
        "source_job_id": "nullable-test-001",
        "url": "https://example.test/jobs/001",
        "title": "Test role",
        "company_name": "Test Co",
        "scraped_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return JobPosting(**defaults)  # type: ignore[arg-type]


def test_pydantic_defaults_description_to_none() -> None:
    posting = _make_posting()
    assert posting.description_html is None
    assert posting.description_text is None


def test_pydantic_accepts_explicit_none() -> None:
    posting = _make_posting(description_html=None, description_text=None)
    assert posting.description_html is None
    assert posting.description_text is None


def test_pydantic_still_accepts_string_descriptions() -> None:
    posting = _make_posting(
        description_html="<p>html body</p>",
        description_text="plain body",
    )
    assert posting.description_html == "<p>html body</p>"
    assert posting.description_text == "plain body"


def test_mapper_orm_to_domain_passes_none_through() -> None:
    orm = JobPostingORM(
        id=uuid4(),
        source="huggingface",
        source_job_id="nullable-mapper-001",
        url="https://example.test/jobs/mapper-001",
        title="Test role",
        company_name="Test Co",
        location_raw=None,
        description_html=None,
        description_text=None,
        posted_at=None,
        scraped_at=datetime.now(UTC),
        raw_payload={},
    )

    posting = _posting_to_domain(orm)

    assert posting.description_html is None
    assert posting.description_text is None


def test_mapper_domain_to_orm_passes_none_through() -> None:
    posting = _make_posting(description_html=None, description_text=None)

    orm = _posting_to_orm(posting)

    assert orm.description_html is None
    assert orm.description_text is None
