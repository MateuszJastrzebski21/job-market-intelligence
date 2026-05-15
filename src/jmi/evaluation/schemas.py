"""Pydantic models for the ground-truth seed file.

The seed file (`docs/ground_truth/phase1_seed.json`) is a JSON array of
hand-labelled job postings. Each entry pairs a posting with the values a
perfect extractor should produce. These models validate that file and feed
the evaluation runner.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from jmi.models.job import EmploymentType, RemotePolicy, Seniority, Source


class GroundTruthPosting(BaseModel):
    """The posting context attached to a seed entry. Human-readable only —
    matching uses `source_job_id`, not these fields."""

    model_config = ConfigDict(extra="ignore")

    title: str
    company: str
    location: str | None = None
    description_text: str | None = None


class GroundTruthExpected(BaseModel):
    """The gold label: the values a perfect extractor should produce.

    `extra="forbid"` so a typo'd field name in the seed file fails loudly
    rather than being silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    seniority: Seniority | None = None
    tech_stack: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    remote_policy: RemotePolicy | None = None
    years_experience_min: int | None = None
    employment_type: EmploymentType | None = None


class GroundTruthEntry(BaseModel):
    """One labelled entry in the seed file.

    `source_job_id` is optional: the original 3 few-shot HF entries predate
    the evaluation framework and carry only a human-readable `id`. Without a
    `source_job_id` the entry cannot be matched to a DB extract — future
    hand-written labels should always include it.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    source: Source
    source_job_id: str | None = None
    posting: GroundTruthPosting
    expected: GroundTruthExpected
    notes: str | None = None


_SEED_ADAPTER: TypeAdapter[list[GroundTruthEntry]] = TypeAdapter(list[GroundTruthEntry])


def parse_seed(raw: str | bytes) -> list[GroundTruthEntry]:
    """Validate raw JSON (a top-level array) into a list of seed entries."""
    return _SEED_ADAPTER.validate_json(raw)
