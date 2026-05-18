from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from jmi.models.job import Source

# Defensive upper bounds on attacker-influenced ingest payloads. Generous
# enough to never reject a legitimate posting; tight enough to bound memory.
_MAX_BATCH_ITEMS = 500
_MAX_DESCRIPTION_CHARS = 500_000


class IngestPostingIn(BaseModel):
    """One job posting captured from a portal listing page."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(max_length=200)
    url: HttpUrl
    title: str = Field(max_length=300)
    company_name: str = Field(max_length=200)
    location_raw: str | None = Field(default=None, max_length=300)
    salary_raw: str | None = Field(default=None, max_length=200)
    posted_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class IngestBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    postings: list[IngestPostingIn] = Field(max_length=_MAX_BATCH_ITEMS)


class InvalidEntry(BaseModel):
    idx: int
    error: str


class IngestBatchOut(BaseModel):
    accepted: int
    skipped_existing: int
    invalid: list[InvalidEntry] = Field(default_factory=list)
    # Indices (in the request `postings` array) that were freshly inserted on
    # this call. Used by the extension SW to know which URLs to forward to
    # INGEST_DETAILS; skipped_existing rows aren't included since their
    # details were filled by a prior run.
    accepted_indices: list[int] = Field(default_factory=list)


class DetailIn(BaseModel):
    """Detail-page result for a previously-ingested posting."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(max_length=200)
    description_html: str = Field(max_length=_MAX_DESCRIPTION_CHARS)
    description_text: str = Field(max_length=_MAX_DESCRIPTION_CHARS)
    raw_payload_patch: dict[str, Any] = Field(default_factory=dict)


class DetailsBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    details: list[DetailIn] = Field(max_length=_MAX_BATCH_ITEMS)


class DetailsBatchOut(BaseModel):
    updated: int
    skipped_unknown: int
    invalid: list[InvalidEntry] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: str
    db_ok: bool
    version: str
