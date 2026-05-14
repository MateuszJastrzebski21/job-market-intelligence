"""Shared fixtures for FastAPI ingest-endpoint tests.

A `TestClient` is constructed against `create_app()` with three dependency
overrides so no real database, settings file, or env var is required:

  - `get_app_settings` → returns a Settings with a known ingest_token
  - `get_posting_repo` → returns an in-memory repo fake (mirrors the public
    surface of `JobPostingRepository` exercised by the routes)
  - `health_db_check` → returns True by default; individual tests can flip it.

The fake mirrors only the methods the routes actually call.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from jmi.api.app import create_app
from jmi.api.deps import get_app_settings, get_posting_repo, health_db_check
from jmi.config import Settings
from jmi.models.job import JobPosting

TEST_TOKEN = "test-token"


class _InMemoryPostingRepo:
    """Matches the slice of JobPostingRepository the routes use."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, JobPosting] = {}
        self._by_source_key: dict[tuple[str, str], JobPosting] = {}

    def add(self, posting: JobPosting) -> JobPosting:
        self._by_id[posting.id] = posting
        self._by_source_key[(posting.source, posting.source_job_id)] = posting
        return posting

    def get_by_source(
        self, source: str, source_job_id: str
    ) -> JobPosting | None:
        return self._by_source_key.get((source, source_job_id))

    def update_description(
        self,
        posting_id: UUID,
        description_html: str,
        description_text: str,
        raw_payload: dict[str, Any],
    ) -> None:
        existing = self._by_id.get(posting_id)
        if existing is None:
            raise KeyError(posting_id)
        updated = existing.model_copy(
            update={
                "description_html": description_html,
                "description_text": description_text,
                "raw_payload": raw_payload,
            }
        )
        self._by_id[posting_id] = updated
        self._by_source_key[(updated.source, updated.source_job_id)] = updated


@pytest.fixture
def in_memory_repo() -> _InMemoryPostingRepo:
    return _InMemoryPostingRepo()


@pytest.fixture
def client(in_memory_repo: _InMemoryPostingRepo) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        ingest_token=TEST_TOKEN
    )
    app.dependency_overrides[get_posting_repo] = lambda: in_memory_repo
    app.dependency_overrides[health_db_check] = lambda: True
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Ingest-Token": TEST_TOKEN}
