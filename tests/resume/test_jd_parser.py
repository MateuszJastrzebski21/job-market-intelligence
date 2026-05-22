"""Tests for ``jmi.resume.jd_parser.parse_jd`` (PR-3.4)."""

from __future__ import annotations

from typing import Any, cast

import anthropic
import pytest

from jmi.resume.jd_parser import JD_PARSER_MODEL, JDTooShortError, parse_jd
from jmi.resume.schemas import JobDescription
from tests.fixtures.anthropic_responses import (
    FakeAnthropic,
    build_parsed_message,
)


def _sample_jd(
    *,
    company_name: str = "Acme",
    language: str = "en",
    seniority: str = "senior",
    raw_url: str | None = None,
) -> JobDescription:
    return JobDescription(
        raw_text="Senior AI Engineer at Acme — Python, RAG pipelines, pgvector.",
        company_name=company_name,
        company_domain="acme.com",
        role_title="Senior AI Engineer",
        seniority=cast(Any, seniority),
        must_have_skills=["Python", "RAG"],
        nice_to_have_skills=["pgvector"],
        location="Warsaw, Poland",
        language=cast(Any, language),
        raw_url=raw_url,
    )


def test_short_jd_raises_before_api_call() -> None:
    fake = FakeAnthropic()  # no responses queued — proves no call
    with pytest.raises(JDTooShortError):
        parse_jd("too short", client=cast(anthropic.Anthropic, fake))


def test_basic_parse_returns_jd_and_telemetry() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_sample_jd())])
    raw = "Senior AI Engineer at Acme — Python, RAG, pgvector. " * 5

    result = parse_jd(raw, client=cast(anthropic.Anthropic, fake))

    assert result.jd.company_name == "Acme"
    assert result.jd.role_title == "Senior AI Engineer"
    assert result.jd.seniority == "senior"
    assert result.model == JD_PARSER_MODEL
    assert result.cost_usd > 0


def test_uses_messages_parse_with_output_format() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_sample_jd())])
    raw = "Senior AI Engineer at Acme — Python, RAG, pgvector. " * 5

    parse_jd(raw, client=cast(anthropic.Anthropic, fake))

    call = fake.messages.recorded_parse_calls[0]
    assert call["model"] == JD_PARSER_MODEL
    assert call["output_format"] is JobDescription


def test_system_prompt_has_cache_control() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_sample_jd())])
    raw = "Senior AI Engineer at Acme. " * 10

    parse_jd(raw, client=cast(anthropic.Anthropic, fake))

    system = fake.messages.recorded_parse_calls[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_override_company_overrides_parsed_value() -> None:
    fake = FakeAnthropic(
        parse_responses=[build_parsed_message(_sample_jd(company_name="Misparsed"))]
    )
    raw = "Some role at the actual right company. " * 10

    result = parse_jd(raw, override_company="Real Company", client=cast(anthropic.Anthropic, fake))

    assert result.jd.company_name == "Real Company"


def test_override_url_sets_raw_url() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_sample_jd(raw_url=None))])
    raw = "Some role description. " * 10

    result = parse_jd(
        raw,
        override_url="https://acme.com/jobs/12345",
        client=cast(anthropic.Anthropic, fake),
    )

    assert result.jd.raw_url == "https://acme.com/jobs/12345"


def test_polish_language_flag_preserved() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_sample_jd(language="pl"))])
    raw = "Starszy inżynier AI w firmie Acme. " * 10

    result = parse_jd(raw, client=cast(anthropic.Anthropic, fake))

    assert result.jd.language == "pl"
