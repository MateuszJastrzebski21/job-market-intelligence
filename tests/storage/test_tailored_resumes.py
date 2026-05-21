"""Round-trip + query tests for ``TailoredResumeRepository`` (PR-3.4a)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from jmi.storage.tailored_resumes import (
    TailoredResumeRepository,
    TailoredResumeRow,
)


def _minimal_row(**overrides: Any) -> TailoredResumeRow:
    """Build a minimally-valid row with sensible defaults; override per test."""
    base: dict[str, Any] = {
        "jd_hash": "a" * 64,
        "jd_text": "Senior AI Engineer at Acme — RAG pipelines, evaluation.",
        "company_name": "Acme",
        "company_domain": "acme.com",
        "role_title": "Senior AI Engineer",
        "bullets_json": [
            {"text": "Built a thing.", "chunk_ids": [str(uuid4())], "confidence": "high"},
        ],
        "cover_letter": "Dear team,\n\nI noticed your launch...\n\nThanks.",
        "cover_letter_meta": {"tone": "conversational", "word_count": 280},
        "research_blob": {"company_name": "Acme", "confidence": "high"},
        "chunk_ids_used": [str(uuid4())],
        "cost_usd": 0.155,
        "total_tokens": 18000,
        "web_search_calls": 2,
        "generation_duration_ms": 42000,
        "model_versions": {"opus": "claude-opus-4-7", "sonnet": "claude-sonnet-4-6"},
    }
    base.update(overrides)
    return TailoredResumeRow(**base)


def test_save_returns_uuid_and_persists(db_session: Session) -> None:
    repo = TailoredResumeRepository(db_session)
    row = _minimal_row()
    saved_id = repo.save(row)
    assert saved_id == row.id
    assert repo.count() == 1


def test_get_round_trips_full_row(db_session: Session) -> None:
    repo = TailoredResumeRepository(db_session)
    chunks = [str(uuid4()), str(uuid4())]
    row = _minimal_row(
        chunk_ids_used=chunks,
        cost_usd=0.1734,
        bullets_json=[
            {"text": "First.", "chunk_ids": [chunks[0]], "confidence": "high"},
            {"text": "Second.", "chunk_ids": [chunks[1]], "confidence": "medium"},
        ],
    )
    saved_id = repo.save(row)
    fetched = repo.get(saved_id)
    assert fetched is not None
    assert fetched.company_name == "Acme"
    assert fetched.chunk_ids_used == chunks
    assert fetched.cost_usd == pytest.approx(0.1734)
    assert len(fetched.bullets_json) == 2
    assert fetched.bullets_json[1]["text"] == "Second."
    assert fetched.web_search_calls == 2
    assert fetched.model_versions["opus"] == "claude-opus-4-7"


def test_get_returns_none_for_missing(db_session: Session) -> None:
    repo = TailoredResumeRepository(db_session)
    assert repo.get(uuid4()) is None


def test_find_by_jd_hash_orders_newest_first(db_session: Session) -> None:
    repo = TailoredResumeRepository(db_session)
    h = "b" * 64
    earliest = datetime(2026, 5, 19, 10, 0, 0)
    middle = datetime(2026, 5, 20, 10, 0, 0)
    latest = datetime(2026, 5, 21, 10, 0, 0)
    for ts, name in [(earliest, "First"), (middle, "Second"), (latest, "Third")]:
        repo.save(_minimal_row(jd_hash=h, created_at=ts, company_name=name))

    results = repo.find_by_jd_hash(h)
    assert [r.company_name for r in results] == ["Third", "Second", "First"]


def test_find_by_jd_hash_empty_when_no_match(db_session: Session) -> None:
    repo = TailoredResumeRepository(db_session)
    repo.save(_minimal_row(jd_hash="a" * 64))
    assert repo.find_by_jd_hash("c" * 64) == []


def test_research_blob_nullable(db_session: Session) -> None:
    repo = TailoredResumeRepository(db_session)
    saved_id = repo.save(_minimal_row(research_blob=None))
    fetched = repo.get(saved_id)
    assert fetched is not None
    assert fetched.research_blob is None


def test_gin_index_supports_chunk_overlap_query(db_session: Session) -> None:
    """The GIN index on ``chunk_ids_used`` powers the ``&&`` overlap operator."""
    repo = TailoredResumeRepository(db_session)
    chunk_a = str(uuid4())
    chunk_b = str(uuid4())
    chunk_c = str(uuid4())
    id_only_a = repo.save(_minimal_row(chunk_ids_used=[chunk_a]))
    id_a_and_b = repo.save(_minimal_row(chunk_ids_used=[chunk_a, chunk_b]))
    repo.save(_minimal_row(chunk_ids_used=[chunk_c]))

    overlap_rows = (
        db_session.execute(
            text("SELECT id FROM tailored_resumes WHERE chunk_ids_used && ARRAY[:c]::varchar[]"),
            {"c": chunk_a},
        )
        .scalars()
        .all()
    )
    assert set(overlap_rows) == {id_only_a, id_a_and_b}
