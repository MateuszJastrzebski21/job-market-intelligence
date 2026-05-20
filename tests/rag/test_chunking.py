"""Tests for the per-section chunker (T1)."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from jmi.models.achievement import Achievement
from jmi.rag.chunking import Chunk, chunk_achievement


def _achievement(
    *,
    title: str = "Sample Title",
    context: str = "Context body.",
    approach: str = "Approach body.",
    impact: str = "Impact body.",
    lessons: str = "Lessons body.",
) -> Achievement:
    return Achievement(
        id=uuid4(),
        title=title,
        source_path=Path("achievements/sample.md"),
        context=context,
        approach=approach,
        impact=impact,
        lessons=lessons,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_full_achievement_yields_four_chunks() -> None:
    chunks = chunk_achievement(_achievement())
    assert len(chunks) == 4
    sections = [c.section for c in chunks]
    assert sections == ["context", "approach", "impact", "lessons"]


def test_chunk_indices_are_dense_from_zero() -> None:
    chunks = chunk_achievement(_achievement())
    assert [c.chunk_index for c in chunks] == [0, 1, 2, 3]


def test_header_format_uses_title_and_display_label() -> None:
    chunks = chunk_achievement(_achievement(title="My Project"))
    # ``lessons`` displays as ``What I learned`` — preserves vault heading.
    assert chunks[0].chunk_text.startswith("[My Project — Context]")
    assert chunks[1].chunk_text.startswith("[My Project — Approach]")
    assert chunks[2].chunk_text.startswith("[My Project — Impact]")
    assert chunks[3].chunk_text.startswith("[My Project — What I learned]")


def test_header_separated_from_body_by_blank_line() -> None:
    chunks = chunk_achievement(_achievement(context="The body text."))
    assert chunks[0].chunk_text == "[Sample Title — Context]\n\nThe body text."


def test_empty_section_is_skipped_and_indices_shift_down() -> None:
    chunks = chunk_achievement(_achievement(context="", approach="A.", impact="I.", lessons="L."))
    assert [c.section for c in chunks] == ["approach", "impact", "lessons"]
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_whitespace_only_section_is_treated_as_empty() -> None:
    chunks = chunk_achievement(_achievement(approach="   \n\t  \n"))
    assert [c.section for c in chunks] == ["context", "impact", "lessons"]


def test_all_empty_yields_empty_list() -> None:
    chunks = chunk_achievement(_achievement(context="", approach="", impact="", lessons=""))
    assert chunks == []


def test_text_for_embedding_matches_chunk_text() -> None:
    # Today the two fields are equal — the separation is a design seam, not a
    # behaviour split. The test pins the current contract so a future divergence
    # is intentional and not an accident.
    for c in chunk_achievement(_achievement()):
        assert c.text_for_embedding == c.chunk_text


def test_achievement_id_propagates_to_every_chunk() -> None:
    fixed_id = UUID("12345678-1234-5678-1234-567812345678")
    a = _achievement()
    a_with_id = a.model_copy(update={"id": fixed_id})
    for c in chunk_achievement(a_with_id):
        assert c.achievement_id == fixed_id


def test_chunk_model_is_frozen() -> None:
    chunks = chunk_achievement(_achievement())
    with pytest.raises(ValidationError):
        # frozen Pydantic model rejects assignment with a ValidationError.
        chunks[0].chunk_index = 99  # type: ignore[misc]


def test_minimal_body_still_passes_min_length() -> None:
    # ``Chunk`` enforces ``min_length=1`` on chunk_text + text_for_embedding.
    # A 1-char body still produces a non-empty header+body, so this just confirms
    # the chunker survives short sections.
    chunks = chunk_achievement(_achievement(context="x"))
    assert chunks[0].chunk_text.endswith("\n\nx")


def test_chunk_is_pydantic_chunk_instance() -> None:
    chunks = chunk_achievement(_achievement())
    assert all(isinstance(c, Chunk) for c in chunks)
