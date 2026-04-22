from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Source = Literal["huggingface", "wellfound"]
Seniority = Literal["junior", "mid", "senior", "staff", "principal", "lead"]
RemotePolicy = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full_time", "contract", "part_time", "internship"]


class JobPosting(BaseModel):
    """Raw scraped posting — what a scraper produces before LLM extraction."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source: Source
    source_job_id: str
    url: HttpUrl
    title: str
    company_name: str
    location_raw: str | None = None
    description_html: str
    description_text: str
    posted_at: datetime | None = None
    scraped_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class JobExtract(BaseModel):
    """Structured output from the LLM extractor. One posting can have many extracts
    (e.g. multiple models, re-runs with improved prompts)."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    job_posting_id: UUID
    seniority: Seniority | None = None
    tech_stack: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    remote_policy: RemotePolicy | None = None
    years_experience_min: int | None = None
    employment_type: EmploymentType | None = None
    model_name: str
    raw_llm_response: dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime
