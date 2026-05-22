"""Tests for ``CoverLetterGenerator`` (PR-3.4d)."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import anthropic
import pytest

from jmi.cover_letter.generator import (
    DEFAULT_MODEL,
    CoverLetterGenerationError,
    CoverLetterGenerator,
)
from jmi.rag.retrieval import ScoredChunk
from jmi.research.schemas import CompanyFact, CompanyResearch
from jmi.resume.schemas import (
    CoverLetterDraft,
    CoverLetterParagraph,
    JobDescription,
)
from tests.fixtures.anthropic_responses import (
    FakeAnthropic,
    FakeParsedMessage,
    FakeUsage,
    build_parsed_message,
)


def _jd() -> JobDescription:
    return JobDescription(
        raw_text="Senior AI Engineer at Acme — Python, RAG.",
        company_name="Acme",
        company_domain="acme.com",
        role_title="Senior AI Engineer",
        seniority="senior",
        must_have_skills=["Python"],
        nice_to_have_skills=["RAG"],
        location="Remote",
        language="en",
        raw_url=None,
    )


def _research(*, confidence: str = "high") -> CompanyResearch:
    return CompanyResearch(
        company_name="Acme",
        one_line_summary="Acme builds RAG agents.",
        recent_news=[
            CompanyFact(
                fact="Launched Vertex agents.",
                source_url="https://acme.com/news",
                recency_estimate="last_30d",
            )
        ],
        confidence=cast(Any, confidence),
        specific_opener_candidates=["I noticed your Vertex launch last month..."],
    )


def _chunk(cid: UUID, text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=cid,
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=0.85,
    )


def _draft(
    *,
    tone: str = "conversational",
    company_specific: bool = True,
    confidence: str = "high",
) -> CoverLetterDraft:
    return CoverLetterDraft(
        paragraphs=[
            CoverLetterParagraph(
                text="I noticed your Vertex launch last month.",
                role="opener",
                specific_company_fact_referenced="Vertex agents launch",
            ),
            CoverLetterParagraph(
                text="My experience building a RAG pipeline aligns with your stack.",
                role="body",
                chunk_ids=[str(uuid4())],
            ),
            CoverLetterParagraph(
                text="Happy to walk through the system.",
                role="closer",
            ),
        ],
        word_count=280,
        company_specific_opener=company_specific,
        research_confidence=cast(Any, confidence),
        tone=cast(Any, tone),
    )


def test_generate_returns_draft_and_telemetry() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_draft())])
    gen = CoverLetterGenerator(client=cast(anthropic.Anthropic, fake))
    chunks = [_chunk(uuid4(), "Built a RAG pipeline.")]

    result = gen.generate(_jd(), _research(), chunks)

    assert result.draft.word_count == 280
    assert result.draft.tone == "conversational"
    assert result.draft.company_specific_opener is True
    assert result.cost_usd > 0


def test_generate_uses_messages_parse_with_output_format() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_draft())])
    gen = CoverLetterGenerator(client=cast(anthropic.Anthropic, fake))
    gen.generate(_jd(), _research(), [_chunk(uuid4(), "x")])

    call = fake.messages.recorded_parse_calls[0]
    assert call["model"] == DEFAULT_MODEL
    assert call["output_format"] is CoverLetterDraft
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_tone_propagated_to_prompt() -> None:
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_draft(tone="startup-casual"))])
    gen = CoverLetterGenerator(client=cast(anthropic.Anthropic, fake))
    gen.generate(_jd(), _research(), [_chunk(uuid4(), "x")], tone="startup-casual")

    user_prompt = fake.messages.recorded_parse_calls[0]["messages"][0]["content"]
    assert "<tone>startup-casual</tone>" in user_prompt


def test_no_research_passes_null_research_to_prompt() -> None:
    fake = FakeAnthropic(
        parse_responses=[build_parsed_message(_draft(company_specific=False, confidence="low"))]
    )
    gen = CoverLetterGenerator(client=cast(anthropic.Anthropic, fake))
    gen.generate(_jd(), None, [_chunk(uuid4(), "x")])

    user_prompt = fake.messages.recorded_parse_calls[0]["messages"][0]["content"]
    assert "null  // no research available" in user_prompt


def test_chunks_passed_with_ids_in_prompt() -> None:
    cid = uuid4()
    fake = FakeAnthropic(parse_responses=[build_parsed_message(_draft())])
    gen = CoverLetterGenerator(client=cast(anthropic.Anthropic, fake))
    gen.generate(_jd(), _research(), [_chunk(cid, "Built X.")])

    user_prompt = fake.messages.recorded_parse_calls[0]["messages"][0]["content"]
    assert str(cid) in user_prompt


def test_parse_returning_none_raises() -> None:
    no_output = FakeParsedMessage(parsed_output=None, usage=FakeUsage())
    fake = FakeAnthropic(parse_responses=[no_output])
    gen = CoverLetterGenerator(client=cast(anthropic.Anthropic, fake))
    with pytest.raises(CoverLetterGenerationError):
        gen.generate(_jd(), _research(), [_chunk(uuid4(), "x")])
