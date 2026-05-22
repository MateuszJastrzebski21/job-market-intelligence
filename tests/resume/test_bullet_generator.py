"""Tests for ``StructuredBulletGenerator`` (PR-3.4c)."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import anthropic
import pytest

from jmi.rag.retrieval import ScoredChunk
from jmi.resume.bullet_generator import (
    DEFAULT_MODEL,
    BulletGenerationError,
    StructuredBulletGenerator,
)
from jmi.resume.schemas import (
    BulletGenerationOutput,
    JobDescription,
    ResumeBullet,
)
from tests.fixtures.anthropic_responses import (
    FakeAnthropic,
    build_parsed_message,
)


def _jd(
    *,
    company: str = "Acme",
    role: str = "Senior AI Engineer",
    must_have: list[str] | None = None,
) -> JobDescription:
    return JobDescription(
        raw_text=f"Senior AI Engineer at {company}. Python, RAG.",
        company_name=company,
        company_domain=None,
        role_title=role,
        seniority="senior",
        must_have_skills=must_have or ["Python", "RAG"],
        nice_to_have_skills=[],
        location=None,
        language="en",
        raw_url=None,
    )


def _chunk(chunk_id: UUID, text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=0.85,
    )


def _bullet(text: str, chunk_ids: list[str], *, contains_metric: bool = False) -> ResumeBullet:
    return ResumeBullet(
        text=text,
        chunk_ids=chunk_ids,
        mapped_jd_requirement="r",
        contains_metric=contains_metric,
        confidence=cast(Any, "high"),
    )


def test_generate_happy_path_returns_validated_bullets() -> None:
    cid1, cid2 = uuid4(), uuid4()
    chunks = [
        _chunk(cid1, "Built a RAG pipeline using pgvector and BGE embeddings."),
        _chunk(cid2, "Implemented a benchmark harness with MRR and recall@k."),
    ]
    output = BulletGenerationOutput(
        bullets=[
            _bullet("Built a RAG pipeline.", [str(cid1)]),
            _bullet("Implemented a benchmark harness.", [str(cid2)]),
        ],
        uncovered_requirements=["machine-learning ops experience"],
    )
    fake = FakeAnthropic(parse_responses=[build_parsed_message(output)])
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))

    result = gen.generate(_jd(), chunks, bullet_count=5)

    assert len(result.output.bullets) == 2
    assert result.retried is False
    assert result.refused_bullet_count == 0
    assert result.output.uncovered_requirements == ["machine-learning ops experience"]
    assert result.cost_usd > 0


def test_generate_uses_messages_parse_with_output_format() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Built X.")]
    output = BulletGenerationOutput(bullets=[_bullet("Built X.", [str(cid)])])
    fake = FakeAnthropic(parse_responses=[build_parsed_message(output)])
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))

    gen.generate(_jd(), chunks)

    call = fake.messages.recorded_parse_calls[0]
    assert call["model"] == DEFAULT_MODEL
    assert call["output_format"] is BulletGenerationOutput
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    # chunk_id must appear inside the user prompt so the model can cite it:
    assert str(cid) in call["messages"][0]["content"]


def test_grounding_failure_triggers_one_retry() -> None:
    """First response has invalid chunk_id; retry produces valid bullets."""
    cid = uuid4()
    chunks = [_chunk(cid, "Built a thing.")]
    invalid_first = BulletGenerationOutput(
        bullets=[_bullet("Built X.", [str(uuid4())])]  # bogus chunk_id
    )
    valid_retry = BulletGenerationOutput(bullets=[_bullet("Built X.", [str(cid)])])
    fake = FakeAnthropic(
        parse_responses=[
            build_parsed_message(invalid_first),
            build_parsed_message(valid_retry),
        ]
    )
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))

    result = gen.generate(_jd(), chunks)

    assert result.retried is True
    assert len(result.output.bullets) == 1
    assert result.output.bullets[0].chunk_ids == [str(cid)]
    # The retry prompt should include feedback about the rejected bullet:
    retry_call = fake.messages.recorded_parse_calls[1]
    assert "retry_feedback" in retry_call["messages"][0]["content"]


def test_retry_still_invalid_bullets_dropped() -> None:
    """First all-invalid; retry produces one valid + one invalid — accept valid, drop invalid."""
    cid = uuid4()
    chunks = [_chunk(cid, "Worked on the auth migration in 2026.")]
    bogus_id = str(uuid4())
    invalid_first = BulletGenerationOutput(bullets=[_bullet("Built X.", [bogus_id])])
    mixed_retry = BulletGenerationOutput(
        bullets=[
            _bullet("Built X.", [str(cid)]),  # valid
            _bullet("Built Y.", [bogus_id]),  # still invalid
        ]
    )
    fake = FakeAnthropic(
        parse_responses=[
            build_parsed_message(invalid_first),
            build_parsed_message(mixed_retry),
        ]
    )
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))

    result = gen.generate(_jd(), chunks)

    assert result.retried is True
    assert len(result.output.bullets) == 1
    assert result.refused_bullet_count == 1


def test_retry_all_invalid_raises_bullet_generation_error() -> None:
    bogus_id = str(uuid4())
    invalid = BulletGenerationOutput(bullets=[_bullet("Built X.", [bogus_id])])
    chunks = [_chunk(uuid4(), "irrelevant chunk text")]
    fake = FakeAnthropic(
        parse_responses=[
            build_parsed_message(invalid),
            build_parsed_message(invalid),  # retry still bad
        ]
    )
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))

    with pytest.raises(BulletGenerationError):
        gen.generate(_jd(), chunks)


def test_empty_chunks_rejected_before_api_call() -> None:
    fake = FakeAnthropic()  # no responses queued — proves no call
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))
    with pytest.raises(ValueError, match="requires chunks"):
        gen.generate(_jd(), [])


def test_bullet_count_out_of_range_rejected() -> None:
    fake = FakeAnthropic()
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))
    chunks = [_chunk(uuid4(), "x")]
    with pytest.raises(ValueError, match="bullet_count must be"):
        gen.generate(_jd(), chunks, bullet_count=3)
    with pytest.raises(ValueError, match="bullet_count must be"):
        gen.generate(_jd(), chunks, bullet_count=11)


def test_verb_elevation_violation_caught_and_retry() -> None:
    """First response says 'Led' but chunk says 'helped'; retry uses 'helped'."""
    cid = uuid4()
    chunks = [_chunk(cid, "Helped with the auth migration.")]
    invalid_first = BulletGenerationOutput(bullets=[_bullet("Led the auth migration.", [str(cid)])])
    valid_retry = BulletGenerationOutput(
        bullets=[_bullet("Helped with the auth migration.", [str(cid)])]
    )
    fake = FakeAnthropic(
        parse_responses=[
            build_parsed_message(invalid_first),
            build_parsed_message(valid_retry),
        ]
    )
    gen = StructuredBulletGenerator(client=cast(anthropic.Anthropic, fake))

    result = gen.generate(_jd(), chunks)
    assert result.retried is True
    assert result.output.bullets[0].text == "Helped with the auth migration."
