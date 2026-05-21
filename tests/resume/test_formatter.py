"""Markdown rendering tests for ``jmi.resume.formatter`` (PR-3.4d)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from jmi.resume.formatter import format_tailored_resume
from jmi.resume.schemas import (
    CoverLetterDraft,
    CoverLetterParagraph,
    JobDescription,
    ResumeBullet,
    TailoredResume,
)


def _jd() -> JobDescription:
    return JobDescription(
        raw_text="Senior AI Engineer at Acme.",
        company_name="Acme",
        company_domain="acme.com",
        role_title="Senior AI Engineer",
        seniority="senior",
        must_have_skills=["Python"],
        nice_to_have_skills=[],
        location=None,
        language="en",
        raw_url=None,
    )


def _bullet(text: str, chunk_id: str | None = None) -> ResumeBullet:
    return ResumeBullet(
        text=text,
        chunk_ids=[chunk_id or str(uuid4())],
        mapped_jd_requirement="r",
        contains_metric=False,
        confidence=cast(Any, "high"),
    )


def _cover_letter(*, company_specific: bool = True) -> CoverLetterDraft:
    return CoverLetterDraft(
        paragraphs=[
            CoverLetterParagraph(
                text="Opening sentence about company.",
                role="opener",
                specific_company_fact_referenced="recent launch",
            ),
            CoverLetterParagraph(
                text="Body paragraph mapping achievements.",
                role="body",
                chunk_ids=[str(uuid4())],
            ),
            CoverLetterParagraph(text="Closing with specific next step.", role="closer"),
        ],
        word_count=280,
        company_specific_opener=company_specific,
        research_confidence=cast(Any, "high"),
        tone=cast(Any, "conversational"),
    )


def _tailored(
    *,
    with_cover_letter: bool = True,
    cover_letter: CoverLetterDraft | None = None,
    uncovered: list[str] | None = None,
) -> TailoredResume:
    return TailoredResume(
        job_description=_jd(),
        bullets=[
            _bullet("Built a RAG pipeline."),
            _bullet("Implemented a benchmark harness."),
        ],
        uncovered_requirements=uncovered or [],
        cover_letter=(cover_letter or _cover_letter()) if with_cover_letter else None,
        company_research=None,
        generated_at=datetime(2026, 5, 21, 10, 0, 0),
        model_versions={"bullet_model": "claude-opus-4-7"},
        cost_usd=0.155,
        total_tokens=18000,
        web_search_calls=1,
        generation_duration_ms=42000,
        chunk_ids_used=[str(uuid4()), str(uuid4())],
        jd_hash="a" * 64,
    )


def test_basic_render_has_header_bullets_and_cover_letter() -> None:
    md = format_tailored_resume(_tailored())
    assert md.startswith("# Senior AI Engineer — Acme\n")
    assert "## Selected Achievements" in md
    assert "- Built a RAG pipeline." in md
    assert "## Cover Letter" in md
    assert "Opening sentence about company." in md
    assert "Closing with specific next step." in md


def test_bullets_only_render_skips_cover_letter() -> None:
    md = format_tailored_resume(_tailored(with_cover_letter=False))
    assert "## Cover Letter" not in md
    assert "## Selected Achievements" in md


def test_uncovered_requirements_render_in_subsection() -> None:
    md = format_tailored_resume(_tailored(uncovered=["MLOps experience"]))
    assert "### Requirements not covered" in md
    assert "- MLOps experience" in md


def test_generic_opener_renders_note_about_low_confidence() -> None:
    cl = _cover_letter(company_specific=False)
    md = format_tailored_resume(_tailored(cover_letter=cl))
    assert "research_confidence=high" in md
    assert "opener is role-generic" in md


def test_include_meta_appends_metadata_section() -> None:
    md = format_tailored_resume(_tailored(), include_meta=True)
    assert "## Generation Metadata" in md
    assert "Cost: $0.1550" in md
    assert "Total tokens: 18,000" in md
    assert "Web search calls: 1" in md
    assert "Duration: 42000 ms" in md


def test_default_render_omits_metadata() -> None:
    md = format_tailored_resume(_tailored())
    assert "## Generation Metadata" not in md


def test_output_ends_with_single_trailing_newline() -> None:
    md = format_tailored_resume(_tailored())
    assert md.endswith("\n")
    assert not md.endswith("\n\n")


def test_no_emoji_in_output_for_ats_safety() -> None:
    """Per dossier §3 / Jobscan 2026: no emoji to avoid ATS NULL substitution."""
    md = format_tailored_resume(_tailored(), include_meta=True)
    # ASCII + basic Latin only (em-dash and ellipsis are fine in markdown but
    # not in emoji ranges)
    assert "📞" not in md
    assert "🚀" not in md
    assert "✅" not in md
