"""Post-hoc validation of generated resume bullets (PR-3.4).

The bullet generator runs ``messages.parse(output_format=BulletGenerationOutput)``
to get schema-valid bullets from Anthropic. The schema enforces shape; this
module enforces *content* — that cited chunk_ids exist in the retrieved set,
that numeric claims trace to chunk text, that the bullet's leading verb does
not elevate scope beyond what the chunks support, and that no deny-listed
phrase appears.

Each ``validate_bullet`` call returns a ``ValidationOutcome`` — the generator
decides what to do (drop, retry, accept) based on the outcome.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from jmi.rag.retrieval import ScoredChunk
from jmi.resume.schemas import ResumeBullet


class ValidationOutcome(StrEnum):
    """Result of validating one bullet."""

    VALID = "valid"
    GROUNDING_ERROR = "grounding_error"
    NUMERIC_ERROR = "numeric_error"
    VERB_ELEVATION_ERROR = "verb_elevation_error"
    DENYLIST_ERROR = "denylist_error"


# Bullet's leading verb → set of phrases that must appear in cited chunk text.
# Empty set means "lateral verb, no support needed" (chunk membership alone is
# sufficient grounding). Unknown verbs default to "no support needed".
VERB_SUPPORT_REQUIREMENTS: dict[str, set[str]] = {
    # Leadership-claim verbs require explicit chunk evidence.
    "led": {"led", "leading", "managed", "owned", "directed", "spearheaded", "drove"},
    "owned": {"owned", "ownership", "led", "managed"},
    "managed": {"managed", "led", "manager"},
    "directed": {"directed", "led", "manager"},
    "drove": {"drove", "led", "owned"},
    "spearheaded": {"spearheaded", "led", "owned"},
    "headed": {"headed", "led", "managed"},
    # Design-claim verbs require explicit chunk evidence.
    "architected": {"architected", "architecture", "designed"},
    "designed": {"designed", "design", "architecture"},
    # Lateral verbs: no chunk-text requirement.
    "built": set(),
    "implemented": set(),
    "developed": set(),
    "wrote": set(),
    "shipped": set(),
    "delivered": set(),
    "created": set(),
    "engineered": set(),
    "contributed": set(),
    "worked": set(),
    "collaborated": set(),
    "supported": set(),
    "helped": set(),
    "researched": set(),
    "analysed": set(),
    "analyzed": set(),
    "investigated": set(),
    "measured": set(),
    "tested": set(),
    "evaluated": set(),
    "improved": set(),
    "optimised": set(),
    "optimized": set(),
    "reduced": set(),
    "increased": set(),
    "scaled": set(),
    "automated": set(),
    "migrated": set(),
    "refactored": set(),
    "fixed": set(),
    "debugged": set(),
    "deployed": set(),
}

# Substrings forbidden anywhere in a bullet (case-insensitive). These are the
# AI-fingerprint phrases per dossier §3.
BULLET_DENYLIST: frozenset[str] = frozenset(
    {
        "responsible for",
        "passionate about",
        "utilised",
        "utilized",  # American spelling — also forbidden
        "synergy",
        "results-driven",
        "team player",
    }
)

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")
_NUMERIC_TOLERANCE = 0.05  # ±5% per dossier §3


@dataclass
class ValidationReport:
    """Per-bullet outcome + the reason, for logging and retry-message construction."""

    outcome: ValidationOutcome
    reason: str | None = None


def validate_bullet(
    bullet: ResumeBullet, retrieved_chunks: Iterable[ScoredChunk]
) -> ValidationReport:
    """Validate one bullet against the retrieved chunk set.

    Returns ``VALID`` only if every rule passes. The first failing rule
    determines the outcome — there is no aggregation of failures because a
    single failure already disqualifies the bullet.
    """
    chunk_by_id = {str(c.chunk_id): c for c in retrieved_chunks}

    # 1. Citation grounding — every chunk_id must be in the retrieved set.
    missing = [cid for cid in bullet.chunk_ids if cid not in chunk_by_id]
    if missing:
        return ValidationReport(
            outcome=ValidationOutcome.GROUNDING_ERROR,
            reason=f"cited chunk_ids not in retrieved set: {missing}",
        )

    cited_blob = " ".join(chunk_by_id[cid].chunk_text.lower() for cid in bullet.chunk_ids)
    bullet_text_lower = bullet.text.lower()

    # 2. Deny-list — banned phrases anywhere in the bullet text.
    for banned in BULLET_DENYLIST:
        if banned in bullet_text_lower:
            return ValidationReport(
                outcome=ValidationOutcome.DENYLIST_ERROR,
                reason=f"banned phrase {banned!r}",
            )

    # 3. Verb elevation — leading verb must be supported by chunk text.
    leading_verb = _leading_verb(bullet.text)
    required = VERB_SUPPORT_REQUIREMENTS.get(leading_verb)
    if required and not any(token in cited_blob for token in required):
        return ValidationReport(
            outcome=ValidationOutcome.VERB_ELEVATION_ERROR,
            reason=(
                f"leading verb {leading_verb!r} requires one of "
                f"{sorted(required)} in cited chunks; none found"
            ),
        )

    # 4. Numeric grounding — every number in a metric-bearing bullet must
    # appear in the cited chunks (exact match OR ±5% if numerically parseable).
    if bullet.contains_metric:
        bullet_numbers = _NUMBER_PATTERN.findall(bullet.text)
        chunk_numbers = _NUMBER_PATTERN.findall(cited_blob)
        for num in bullet_numbers:
            if not _number_supported(num, chunk_numbers, cited_blob):
                return ValidationReport(
                    outcome=ValidationOutcome.NUMERIC_ERROR,
                    reason=f"numeric claim {num!r} not supported by cited chunks",
                )

    return ValidationReport(outcome=ValidationOutcome.VALID)


def _leading_verb(bullet_text: str) -> str:
    """First word, lower-cased, with trailing punctuation stripped."""
    stripped = bullet_text.strip()
    if not stripped:
        return ""
    first = stripped.split(None, 1)[0]
    return first.lower().rstrip(",.;:!?")


def _number_supported(bullet_num: str, chunk_numbers: list[str], chunk_blob: str) -> bool:
    """Match exact OR within ±5% (numeric) OR substring (e.g. version numbers)."""
    if bullet_num in chunk_blob:
        return True
    bullet_val = _parse_number(bullet_num)
    if bullet_val is None:
        return False
    for chunk_num in chunk_numbers:
        chunk_val = _parse_number(chunk_num)
        if chunk_val is None or chunk_val == 0:
            continue
        if abs(bullet_val - chunk_val) / max(abs(chunk_val), 1.0) <= _NUMERIC_TOLERANCE:
            return True
    return False


def _parse_number(num_str: str) -> float | None:
    try:
        return float(num_str.rstrip("%"))
    except ValueError:
        return None
