"""Pydantic schemas for the resume generator (PR-3.4).

Boundary types between the LLM-facing generators and the orchestration layer.
``JobDescription`` is populated by the JD parser (lands here); the bullet +
cover-letter + tailored-resume schemas land in PR-3.4c and PR-3.4d.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobDescription(BaseModel):
    """Parsed structure of a job description.

    Boundary: every field must be filled by the parser from the source JD; no
    defaults that hide missing data. ``unknown`` seniority + empty skill lists
    are valid outcomes for sparse JDs.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    raw_text: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    company_domain: str | None = None
    role_title: str = Field(min_length=1)
    seniority: Literal["junior", "mid", "senior", "staff", "principal", "unknown"]
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    location: str | None = None
    language: Literal["en", "pl", "other"]
    raw_url: str | None = None
