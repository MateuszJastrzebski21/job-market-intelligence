"""Structured resume-bullet generator (PR-3.4).

``StructuredBulletGenerator`` co-exists with the existing
``jmi.rag.generation.Generator`` (PR-3.2's plain-text generator used by the
``rag-query`` CLI command). The new class uses ``messages.parse()`` with the
``BulletGenerationOutput`` schema so bullets arrive validated-by-construction;
a post-hoc bullet_validator then checks chunk-grounding, numeric claims,
verb-elevation, and the deny-list.

On grounding failure: one retry with a clarifying user message. After the
retry, any still-invalid bullets are dropped from the output (and reported in
``refused_bullet_count``) rather than blocking the whole generation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

import anthropic
import structlog

from jmi.config import get_settings
from jmi.costs import estimate_cost
from jmi.rag.retrieval import ScoredChunk
from jmi.resume.bullet_validator import (
    ValidationOutcome,
    ValidationReport,
    validate_bullet,
)
from jmi.resume.prompts import BULLET_SYSTEM_PROMPT
from jmi.resume.schemas import (
    BulletGenerationOutput,
    JobDescription,
    ResumeBullet,
)

log = structlog.get_logger(__name__)

DEFAULT_MODEL: Final[str] = "claude-opus-4-7"
DEFAULT_MAX_TOKENS: Final[int] = 2000
DEFAULT_BULLET_COUNT: Final[int] = 6
MIN_BULLET_COUNT: Final[int] = 5
MAX_BULLET_COUNT: Final[int] = 10


class BulletGenerationError(RuntimeError):
    """Raised when even the retry produced zero valid bullets — there is nothing
    to return and the caller should abort the generation."""


@dataclass
class BulletGenerationResult:
    """Return value of ``StructuredBulletGenerator.generate``."""

    output: BulletGenerationOutput
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    refused_bullet_count: int
    retried: bool


@dataclass
class _RawCallResult:
    output: BulletGenerationOutput
    input_tokens: int
    output_tokens: int
    cost_usd: float


class StructuredBulletGenerator:
    """Opus 4.7 + ``messages.parse(BulletGenerationOutput)``."""

    def __init__(
        self,
        *,
        client: anthropic.Anthropic | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        if client is None:
            api_key = get_settings().anthropic_api_key
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Add it to .env (copy from "
                    ".env.example) before invoking the bullet generator."
                )
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def generate(
        self,
        jd: JobDescription,
        chunks: list[ScoredChunk],
        *,
        bullet_count: int = DEFAULT_BULLET_COUNT,
    ) -> BulletGenerationResult:
        if not (MIN_BULLET_COUNT <= bullet_count <= MAX_BULLET_COUNT):
            raise ValueError(
                f"bullet_count must be in [{MIN_BULLET_COUNT},{MAX_BULLET_COUNT}], "
                f"got {bullet_count}"
            )
        if not chunks:
            raise ValueError("StructuredBulletGenerator.generate requires chunks")

        log.info(
            "resume.bullets.start",
            company=jd.company_name,
            role=jd.role_title,
            chunk_count=len(chunks),
            bullet_count=bullet_count,
        )

        first = self._call(jd, chunks, bullet_count=bullet_count)
        validated = [(b, validate_bullet(b, chunks)) for b in first.output.bullets]
        valid_first = [b for b, report in validated if report.outcome is ValidationOutcome.VALID]
        invalid_first = [(b, r) for b, r in validated if r.outcome is not ValidationOutcome.VALID]

        if not invalid_first:
            log.info(
                "resume.bullets.done",
                accepted=len(valid_first),
                refused=0,
                retried=False,
            )
            return BulletGenerationResult(
                output=BulletGenerationOutput(
                    bullets=valid_first,
                    uncovered_requirements=first.output.uncovered_requirements,
                ),
                input_tokens=first.input_tokens,
                output_tokens=first.output_tokens,
                cost_usd=first.cost_usd,
                model=self._model,
                refused_bullet_count=0,
                retried=False,
            )

        # Retry once with a feedback message listing every invalid bullet.
        log.warning(
            "resume.bullets.retry",
            invalid_count=len(invalid_first),
            reasons=[r.reason for _, r in invalid_first if r.reason],
        )
        retry_feedback = _describe_invalid(invalid_first)
        second = self._call(jd, chunks, bullet_count=bullet_count, retry_feedback=retry_feedback)
        validated2 = [(b, validate_bullet(b, chunks)) for b in second.output.bullets]
        valid_second = [b for b, r in validated2 if r.outcome is ValidationOutcome.VALID]
        refused_second = len(validated2) - len(valid_second)

        if not valid_second:
            raise BulletGenerationError(
                "Even after one retry, no bullet passed validation. The model is "
                "unable to ground bullets in the supplied chunks; aborting."
            )

        log.info(
            "resume.bullets.done",
            accepted=len(valid_second),
            refused=refused_second,
            retried=True,
        )
        return BulletGenerationResult(
            output=BulletGenerationOutput(
                bullets=valid_second,
                uncovered_requirements=second.output.uncovered_requirements,
            ),
            input_tokens=first.input_tokens + second.input_tokens,
            output_tokens=first.output_tokens + second.output_tokens,
            cost_usd=first.cost_usd + second.cost_usd,
            model=self._model,
            refused_bullet_count=refused_second,
            retried=True,
        )

    def _call(
        self,
        jd: JobDescription,
        chunks: list[ScoredChunk],
        *,
        bullet_count: int,
        retry_feedback: str | None = None,
    ) -> _RawCallResult:
        user_prompt = _build_user_prompt(jd, chunks, bullet_count, retry_feedback)
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": BULLET_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
            output_format=BulletGenerationOutput,
        )

        parsed = response.parsed_output
        if parsed is None:
            raise BulletGenerationError(
                "Bullet generator returned no parsed_output. The model returned "
                "malformed JSON for BulletGenerationOutput."
            )

        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cost = estimate_cost(
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

        return _RawCallResult(
            output=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


def _build_user_prompt(
    jd: JobDescription,
    chunks: list[ScoredChunk],
    bullet_count: int,
    retry_feedback: str | None,
) -> str:
    chunks_blob = "\n\n".join(
        f'<chunk id="{c.chunk_id}">\n{c.chunk_text}\n</chunk>' for c in chunks
    )
    jd_blob = json.dumps(
        {
            "company_name": jd.company_name,
            "role_title": jd.role_title,
            "seniority": jd.seniority,
            "must_have_skills": jd.must_have_skills,
            "nice_to_have_skills": jd.nice_to_have_skills,
            "raw_text": jd.raw_text,
        },
        indent=2,
    )
    parts = [
        f"<job_description>\n{jd_blob}\n</job_description>",
        f"<retrieved_chunks>\n{chunks_blob}\n</retrieved_chunks>",
        f"Produce exactly {bullet_count} bullets unless you cannot find {bullet_count} "
        "JD requirements that the chunks support — in which case produce fewer and "
        "list the uncovered requirements in uncovered_requirements.",
    ]
    if retry_feedback:
        parts.append(f"<retry_feedback>\n{retry_feedback}\n</retry_feedback>")
    return "\n\n".join(parts)


def _describe_invalid(invalid: list[tuple[ResumeBullet, ValidationReport]]) -> str:
    """Build a human-readable list of why each rejected bullet failed.

    The retry sees this and is told to regenerate ONLY the failing bullets,
    keeping any valid ones intact. (In practice the model re-emits everything;
    the validator runs again and only valid ones survive.)
    """
    lines = ["The following bullets were rejected by the post-hoc validator:"]
    for bullet, report in invalid:
        lines.append(
            f"- {report.outcome.value}: {bullet.text!r} — {report.reason or '(no reason)'}"
        )
    lines.append(
        "Regenerate the rejected bullets only, fixing the issues. Keep "
        "bullets that were not in this list unchanged."
    )
    return "\n".join(lines)
