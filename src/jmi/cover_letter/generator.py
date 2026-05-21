"""Cover letter generator (PR-3.4).

Opus 4.7 + ``messages.parse(output_format=CoverLetterDraft)``. Consumes JD,
optional ``CompanyResearch``, retrieved achievement chunks, and a tone. When
research is absent OR research.confidence is ``"low"``, the prompt instructs
the model to skip the company-specific opener and use a generic-but-
personalised role-focused opener instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

import anthropic
import structlog

from jmi.config import get_settings
from jmi.costs import estimate_cost
from jmi.cover_letter.prompts import COVER_LETTER_SYSTEM_PROMPT
from jmi.rag.retrieval import ScoredChunk
from jmi.research.schemas import CompanyResearch
from jmi.resume.schemas import CoverLetterDraft, JobDescription, Tone

log = structlog.get_logger(__name__)

DEFAULT_MODEL: Final[str] = "claude-opus-4-7"
DEFAULT_MAX_TOKENS: Final[int] = 1500
DEFAULT_TONE: Final[Tone] = "conversational"


class CoverLetterGenerationError(RuntimeError):
    """Raised when the cover letter generator returns no ``parsed_output``."""


@dataclass
class CoverLetterGenerationResult:
    """Return value of ``CoverLetterGenerator.generate``."""

    draft: CoverLetterDraft
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


class CoverLetterGenerator:
    """Opus 4.7 + ``messages.parse(CoverLetterDraft)``. Tone-aware."""

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
                    ".env.example) before invoking the cover letter generator."
                )
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def generate(
        self,
        jd: JobDescription,
        research: CompanyResearch | None,
        chunks: list[ScoredChunk],
        *,
        tone: Tone = DEFAULT_TONE,
    ) -> CoverLetterGenerationResult:
        log.info(
            "resume.cover_letter.start",
            company=jd.company_name,
            tone=tone,
            research_confidence=(research.confidence if research else "none"),
            chunk_count=len(chunks),
        )

        user_prompt = _build_user_prompt(jd, research, chunks, tone)
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": COVER_LETTER_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
            output_format=CoverLetterDraft,
        )

        parsed = response.parsed_output
        if parsed is None:
            raise CoverLetterGenerationError("Cover letter generator returned no parsed_output.")

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

        log.info(
            "resume.cover_letter.done",
            word_count=parsed.word_count,
            company_specific_opener=parsed.company_specific_opener,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

        return CoverLetterGenerationResult(
            draft=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=self._model,
        )


def _build_user_prompt(
    jd: JobDescription,
    research: CompanyResearch | None,
    chunks: list[ScoredChunk],
    tone: Tone,
) -> str:
    jd_blob = json.dumps(
        {
            "company_name": jd.company_name,
            "company_domain": jd.company_domain,
            "role_title": jd.role_title,
            "seniority": jd.seniority,
            "must_have_skills": jd.must_have_skills,
            "nice_to_have_skills": jd.nice_to_have_skills,
            "raw_text": jd.raw_text,
        },
        indent=2,
    )
    if research is None:
        research_blob = "null  // no research available; use generic opener"
    else:
        research_blob = research.model_dump_json(indent=2)
    chunks_blob = "\n\n".join(
        f'<chunk id="{c.chunk_id}">\n{c.chunk_text}\n</chunk>' for c in chunks
    )
    return (
        f"<job_description>\n{jd_blob}\n</job_description>\n\n"
        f"<company_research>\n{research_blob}\n</company_research>\n\n"
        f"<retrieved_achievements>\n{chunks_blob}\n</retrieved_achievements>\n\n"
        f"<tone>{tone}</tone>\n\n"
        "Draft the cover letter following the system prompt rules. Return a "
        "CoverLetterDraft."
    )
