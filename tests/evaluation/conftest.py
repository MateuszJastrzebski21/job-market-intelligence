"""Fixtures for the evaluation suite.

Consistent with the rest of the test suite (tests/api/conftest.py), this uses
in-memory fake repositories — no Postgres, no testcontainers. The real-DB path
is covered by the manual smoke test (`uv run jmi evaluate`).
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from jmi.evaluation.schemas import GroundTruthEntry
from jmi.models.job import JobExtract, JobPosting


class FakeJobPostingRepository:
    """In-memory stand-in exposing the slice the runner uses."""

    def __init__(self) -> None:
        self._by_source_key: dict[tuple[str, str], JobPosting] = {}

    def add(self, posting: JobPosting) -> JobPosting:
        self._by_source_key[(posting.source, posting.source_job_id)] = posting
        return posting

    def get_by_source(
        self, source: str, source_job_id: str
    ) -> JobPosting | None:
        return self._by_source_key.get((source, source_job_id))


class FakeJobExtractRepository:
    """In-memory stand-in; list_by_posting mirrors the real extracted_at DESC."""

    def __init__(self) -> None:
        self._by_posting: dict[UUID, list[JobExtract]] = {}

    def add(self, extract: JobExtract) -> JobExtract:
        self._by_posting.setdefault(extract.job_posting_id, []).append(extract)
        return extract

    def list_by_posting(self, posting_id: UUID) -> list[JobExtract]:
        rows = self._by_posting.get(posting_id, [])
        return sorted(rows, key=lambda e: e.extracted_at, reverse=True)


@pytest.fixture
def posting_repo() -> FakeJobPostingRepository:
    return FakeJobPostingRepository()


@pytest.fixture
def extract_repo() -> FakeJobExtractRepository:
    return FakeJobExtractRepository()


@pytest.fixture
def make_posting() -> Callable[..., JobPosting]:
    def _make(**overrides: object) -> JobPosting:
        defaults: dict[str, object] = {
            "source": "huggingface",
            "source_job_id": "JOB-001",
            "url": "https://example.test/jobs/001",
            "title": "ML Engineer",
            "company_name": "Acme",
            "scraped_at": datetime.now(UTC),
        }
        defaults.update(overrides)
        return JobPosting(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_extract() -> Callable[..., JobExtract]:
    def _make(**overrides: object) -> JobExtract:
        defaults: dict[str, object] = {
            "job_posting_id": uuid4(),
            "model_name": "claude-opus-4-7",
            "extracted_at": datetime.now(UTC),
        }
        defaults.update(overrides)
        return JobExtract(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_entry() -> Callable[..., GroundTruthEntry]:
    def _make(**overrides: object) -> GroundTruthEntry:
        defaults: dict[str, object] = {
            "id": "hf-TESTLABEL1",
            "source": "huggingface",
            "source_job_id": "JOB-001",
            "posting": {"title": "ML Engineer", "company": "Acme"},
            "expected": {},
        }
        defaults.update(overrides)
        return GroundTruthEntry.model_validate(defaults)

    return _make


@pytest.fixture
def sample_seed_file(tmp_path: Path) -> Path:
    """A small valid seed file on disk, for exercising load_seed."""
    entries = [
        {
            "id": "hf-AAAAAAAAAA",
            "source": "huggingface",
            "source_job_id": "JOB-AAA",
            "posting": {"title": "ML Engineer", "company": "Acme"},
            "expected": {
                "seniority": "senior",
                "tech_stack": ["Python", "PyTorch"],
                "remote_policy": "remote",
            },
            "notes": "labelled with source_job_id",
        },
        {
            "id": "hf-BBBBBBBBBB",
            "source": "huggingface",
            "posting": {"title": "Data Scientist", "company": "Acme"},
            "expected": {"seniority": "mid"},
            "notes": "id-only few-shot entry, no source_job_id",
        },
    ]
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


@pytest.fixture
def older_then_newer() -> tuple[datetime, datetime]:
    """A pair of timestamps for latest-extract-wins tests."""
    now = datetime.now(UTC)
    return now - timedelta(days=2), now
