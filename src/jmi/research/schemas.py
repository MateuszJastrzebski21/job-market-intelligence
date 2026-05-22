"""Pydantic schemas for company research (PR-3.4).

``CompanyResearch`` is the structured output of the synthesis call (Call 2 of
the two-call research architecture). Used by the cover-letter generator to
ground its opener in a specific, verified fact.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyFact(BaseModel):
    """One discrete fact about a company, with provenance where available.

    ``source_url`` is plain ``str | None`` rather than ``HttpUrl`` so research
    that comes back with malformed URLs (URL-encoded paths, missing schemes)
    doesn't blow up the whole synthesis — a non-URL string is still useful
    audit trail. A separate validation step can flag invalid URLs.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    fact: str = Field(min_length=1, max_length=400)
    source_url: str | None = Field(
        default=None,
        description="URL from web_search results. Null only if from prior knowledge.",
    )
    recency_estimate: Literal["last_30d", "last_90d", "last_year", "older", "unknown"]


class CompanyResearch(BaseModel):
    """Structured summary of one research pass on a target company.

    ``confidence`` gates downstream behaviour: ``low`` triggers the
    generic-opener fallback path in the cover-letter generator so we never
    output a confidently wrong specific opener for an obscure company.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    company_name: str = Field(min_length=1)
    one_line_summary: str = Field(min_length=1, max_length=300)
    mission_or_thesis: CompanyFact | None = None
    recent_news: list[CompanyFact] = Field(default_factory=list, max_length=5)
    tech_stack_signals: list[CompanyFact] = Field(default_factory=list, max_length=5)
    culture_signals: list[CompanyFact] = Field(default_factory=list, max_length=5)
    hiring_signals: list[CompanyFact] = Field(default_factory=list, max_length=5)
    specific_opener_candidates: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "Candidate first-paragraph sentences each referencing a specific "
            "fact above. Empty when confidence is 'low'."
        ),
    )
    confidence: Literal["high", "medium", "low"]
    search_queries_used: list[str] = Field(default_factory=list)
    notes: str | None = Field(
        default=None,
        description="Free-form note from the synthesis step, e.g. why confidence is low.",
    )
