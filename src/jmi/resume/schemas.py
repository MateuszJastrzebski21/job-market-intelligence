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


class ResumeBullet(BaseModel):
    """One bullet of the tailored resume, with citations and metric flag.

    ``chunk_ids`` are stringified UUIDs of ``achievement_embeddings.id`` PKs.
    Validated post-hoc against the retrieved chunk set — see
    ``jmi.resume.bullet_validator.validate_bullet``.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    text: str = Field(min_length=1, max_length=280)
    chunk_ids: list[str] = Field(min_length=1, max_length=3)
    mapped_jd_requirement: str = Field(min_length=1, max_length=200)
    contains_metric: bool
    confidence: Literal["high", "medium", "low"]


class BulletGenerationOutput(BaseModel):
    """Wrapper for the structured-output target.

    Anthropic's ``messages.parse(output_format=...)`` expects a single root
    Pydantic model — a bare ``list[ResumeBullet]`` doesn't fit. The wrapper
    also carries ``uncovered_requirements``: JD requirements the model could
    not ground in any retrieved chunk and consciously refused to invent
    bullets for.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    bullets: list[ResumeBullet] = Field(min_length=1, max_length=10)
    uncovered_requirements: list[str] = Field(default_factory=list)
