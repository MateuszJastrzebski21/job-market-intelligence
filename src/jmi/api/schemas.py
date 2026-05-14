from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from jmi.models.job import Source


class IngestPostingIn(BaseModel):
    """One job posting captured from a portal listing page."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    url: HttpUrl
    title: str
    company_name: str
    location_raw: str | None = None
    salary_raw: str | None = None
    posted_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class IngestBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    postings: list[IngestPostingIn]


class InvalidEntry(BaseModel):
    idx: int
    error: str


class IngestBatchOut(BaseModel):
    accepted: int
    skipped_existing: int
    invalid: list[InvalidEntry] = Field(default_factory=list)


class DetailIn(BaseModel):
    """Detail-page result for a previously-ingested posting."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    description_html: str
    description_text: str
    raw_payload_patch: dict[str, Any] = Field(default_factory=dict)


class DetailsBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    details: list[DetailIn]


class DetailsBatchOut(BaseModel):
    updated: int
    skipped_unknown: int
    invalid: list[InvalidEntry] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: str
    db_ok: bool
    version: str
