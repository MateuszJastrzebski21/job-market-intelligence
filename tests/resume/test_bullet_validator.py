"""Per-rule tests for ``jmi.resume.bullet_validator`` (PR-3.4c).

Every rule has a positive test (clean bullet passes) and a negative test
(rule trips). Tests for the rule are isolated — one rule per failure path.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from jmi.rag.retrieval import ScoredChunk
from jmi.resume.bullet_validator import (
    BULLET_DENYLIST,
    VERB_SUPPORT_REQUIREMENTS,
    ValidationOutcome,
    validate_bullet,
)
from jmi.resume.schemas import ResumeBullet


def _chunk(chunk_id: UUID, text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=0.85,
    )


def _bullet(
    text: str,
    chunk_ids: list[str],
    *,
    contains_metric: bool = False,
    confidence: str = "high",
) -> ResumeBullet:
    return ResumeBullet(
        text=text,
        chunk_ids=chunk_ids,
        mapped_jd_requirement="some JD requirement",
        contains_metric=contains_metric,
        confidence=cast_confidence(confidence),
    )


def cast_confidence(value: str) -> Any:
    return value


# ── Grounding ────────────────────────────────────────────────────────────────


def test_valid_bullet_with_existing_chunk_id() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Built a Python RAG pipeline with pgvector and bge embeddings.")]
    bullet = _bullet("Built a RAG pipeline.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_grounding_error_when_chunk_id_not_in_retrieved_set() -> None:
    cid_actual = uuid4()
    cid_invented = str(uuid4())
    chunks = [_chunk(cid_actual, "Built something real.")]
    bullet = _bullet("Built a thing.", [cid_invented])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.GROUNDING_ERROR
    assert "not in retrieved set" in (report.reason or "")


# ── Deny-list ────────────────────────────────────────────────────────────────


def test_denylist_responsible_for_rejected() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Worked on the auth migration.")]
    bullet = _bullet("Responsible for the auth migration.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.DENYLIST_ERROR


def test_denylist_passionate_about_rejected() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Worked on Python services.")]
    bullet = _bullet("Built Python services and was passionate about scaling them.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.DENYLIST_ERROR


def test_denylist_utilised_both_spellings_rejected() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Used Python widely.")]
    for variant in ("utilised", "utilized"):
        bullet = _bullet(f"Built systems and {variant} Python.", [str(cid)])
        report = validate_bullet(bullet, chunks)
        assert report.outcome is ValidationOutcome.DENYLIST_ERROR


def test_denylist_contains_all_dossier_phrases() -> None:
    for phrase in ("responsible for", "passionate about", "utilised", "synergy", "team player"):
        assert phrase in BULLET_DENYLIST


# ── Verb elevation ───────────────────────────────────────────────────────────


def test_led_requires_chunk_evidence_of_leadership_negative() -> None:
    """Bullet claims 'Led' but chunk only says 'contributed to'."""
    cid = uuid4()
    chunks = [_chunk(cid, "Contributed to the auth migration in 2025.")]
    bullet = _bullet("Led the auth migration.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VERB_ELEVATION_ERROR
    assert "leading verb 'led'" in (report.reason or "")


def test_led_allowed_when_chunk_says_led() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Led the auth migration in 2025 across three services.")]
    bullet = _bullet("Led the auth migration across three services.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_led_allowed_when_chunk_says_managed() -> None:
    """The 'led' verb is supported by synonyms — 'managed' counts."""
    cid = uuid4()
    chunks = [_chunk(cid, "Managed a 4-engineer team building the auth service.")]
    bullet = _bullet("Led a 4-engineer team on the auth service.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_owned_requires_chunk_evidence_negative() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Helped build the deploy pipeline.")]
    bullet = _bullet("Owned the deploy pipeline.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VERB_ELEVATION_ERROR


def test_architected_requires_chunk_evidence_negative() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Built the worker pool using existing patterns.")]
    bullet = _bullet("Architected the worker pool.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VERB_ELEVATION_ERROR


def test_architected_allowed_when_chunk_mentions_architecture() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Designed the architecture of the worker pool, then implemented it.")]
    bullet = _bullet("Architected the worker pool.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_lateral_verbs_pass_without_special_chunk_evidence() -> None:
    """Lateral verbs like 'built', 'implemented' need only chunk membership."""
    cid = uuid4()
    chunks = [_chunk(cid, "Some achievement text that does not contain the verb.")]
    for verb in ("built", "implemented", "wrote", "developed", "contributed", "worked"):
        bullet = _bullet(f"{verb.capitalize()} a thing.", [str(cid)])
        report = validate_bullet(bullet, chunks)
        assert report.outcome is ValidationOutcome.VALID, (
            f"lateral verb {verb!r} should pass without chunk verb evidence; "
            f"got {report.outcome.value}: {report.reason}"
        )


def test_unknown_verb_does_not_block() -> None:
    """Verbs we haven't catalogued default to no-support-needed."""
    cid = uuid4()
    chunks = [_chunk(cid, "Some text.")]
    bullet = _bullet("Orchestrated a system upgrade.", [str(cid)])
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_verb_support_requirements_table_contains_leadership_verbs() -> None:
    for verb in ("led", "owned", "managed", "directed", "drove", "spearheaded"):
        assert verb in VERB_SUPPORT_REQUIREMENTS
        assert VERB_SUPPORT_REQUIREMENTS[verb], f"{verb} must require explicit support"


# ── Numeric grounding ────────────────────────────────────────────────────────


def test_metric_unsupported_by_chunk_rejected() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Reduced latency by 20% in production.")]
    bullet = _bullet(
        "Reduced latency by 80% in production.",
        [str(cid)],
        contains_metric=True,
    )
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.NUMERIC_ERROR
    assert "80" in (report.reason or "")


def test_metric_within_5_percent_tolerance_accepted() -> None:
    """Chunk says 30%, bullet says 31% — within 5% tolerance."""
    cid = uuid4()
    chunks = [_chunk(cid, "Reduced latency by 30% in production.")]
    bullet = _bullet(
        "Reduced latency by 31% in production.",
        [str(cid)],
        contains_metric=True,
    )
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_exact_metric_match_accepted() -> None:
    cid = uuid4()
    chunks = [_chunk(cid, "Reduced cost by 42% across 10 services.")]
    bullet = _bullet(
        "Reduced cost by 42%.",
        [str(cid)],
        contains_metric=True,
    )
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID


def test_numbers_with_contains_metric_false_not_validated() -> None:
    """A bullet that has numbers but contains_metric=False (e.g. years) is not checked."""
    cid = uuid4()
    chunks = [_chunk(cid, "Worked on the system from 2023 onward.")]
    bullet = _bullet(
        "Built a system in 2099.",  # year not in chunks
        [str(cid)],
        contains_metric=False,  # signals "no impact metric"
    )
    report = validate_bullet(bullet, chunks)
    assert report.outcome is ValidationOutcome.VALID
