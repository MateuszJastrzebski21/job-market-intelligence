"""Pydantic schema tests for ``jmi.research.schemas`` (PR-3.4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jmi.research.schemas import CompanyFact, CompanyResearch


def test_company_fact_requires_recency_estimate() -> None:
    with pytest.raises(ValidationError):
        CompanyFact(
            fact="Acme launched X.", source_url="https://acme.com", recency_estimate="bogus"
        )  # type: ignore[arg-type]


def test_company_fact_accepts_null_source_url() -> None:
    fact = CompanyFact(fact="Acme is a household name.", source_url=None, recency_estimate="older")
    assert fact.source_url is None


def test_company_fact_rejects_overlong_fact() -> None:
    with pytest.raises(ValidationError):
        CompanyFact(fact="x" * 401, source_url=None, recency_estimate="unknown")


def test_company_research_minimal_valid() -> None:
    cr = CompanyResearch(
        company_name="Acme",
        one_line_summary="A company.",
        confidence="low",
    )
    assert cr.recent_news == []
    assert cr.specific_opener_candidates == []


def test_company_research_caps_list_lengths() -> None:
    fact = CompanyFact(fact="x", source_url=None, recency_estimate="unknown")
    with pytest.raises(ValidationError):
        CompanyResearch(
            company_name="Acme",
            one_line_summary="y",
            recent_news=[fact] * 6,  # max_length=5
            confidence="high",
        )


def test_company_research_caps_opener_candidates() -> None:
    with pytest.raises(ValidationError):
        CompanyResearch(
            company_name="Acme",
            one_line_summary="y",
            specific_opener_candidates=["a", "b", "c", "d"],
            confidence="high",
        )


def test_company_research_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        CompanyResearch(  # type: ignore[call-arg]
            company_name="Acme",
            one_line_summary="y",
            confidence="low",
            unexpected_field="boom",
        )
