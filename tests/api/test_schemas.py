"""Tests for ingest-schema size limits (Field max_length constraints)."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from jmi.api.schemas import DetailIn, DetailsBatchIn, IngestBatchIn, IngestPostingIn


def _posting(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_id": "s-1",
        "url": "https://justjoin.it/job-offer/example",
        "title": "Python Developer",
        "company_name": "Acme",
    }
    base.update(overrides)
    return base


def test_ingest_batch_accepts_500_postings() -> None:
    batch = IngestBatchIn(
        source="jjit",
        postings=[_posting(source_id=f"s-{i}") for i in range(500)],
    )
    assert len(batch.postings) == 500


def test_ingest_batch_rejects_501_postings() -> None:
    with pytest.raises(ValidationError):
        IngestBatchIn(
            source="jjit",
            postings=[_posting(source_id=f"s-{i}") for i in range(501)],
        )


def test_ingest_posting_rejects_oversized_title() -> None:
    with pytest.raises(ValidationError):
        IngestPostingIn(**_posting(title="x" * 1000))


def test_details_batch_rejects_501_details() -> None:
    detail = {
        "source_id": "d-1",
        "description_html": "<p>x</p>",
        "description_text": "x",
    }
    with pytest.raises(ValidationError):
        DetailsBatchIn(source="jjit", details=[detail] * 501)


def test_detail_rejects_oversized_description_html() -> None:
    with pytest.raises(ValidationError):
        DetailIn(
            source_id="d-1",
            description_html="x" * 500_001,
            description_text="ok",
        )


def test_detail_rejects_oversized_description_text() -> None:
    with pytest.raises(ValidationError):
        DetailIn(
            source_id="d-1",
            description_html="<p>ok</p>",
            description_text="x" * 500_001,
        )
