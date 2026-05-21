"""Parse a raw job-description string into a structured ``JobDescription``.

Uses Sonnet 4.6 + ``messages.parse()`` — JD parsing is purely extractive so
the cheaper model is fine. Cache-control on the system prompt amortises cost
across repeat runs within the 5-min ephemeral window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import anthropic
import structlog

from jmi.config import get_settings
from jmi.costs import estimate_cost
from jmi.resume.schemas import JobDescription

log = structlog.get_logger(__name__)

JD_PARSER_MODEL: Final[str] = "claude-sonnet-4-6"
JD_PARSER_MAX_TOKENS: Final[int] = 1000
JD_PARSER_PROMPT_VERSION: Final[str] = "jd_parse_2026_05_v1"

MIN_JD_LENGTH = 50

JD_PARSER_SYSTEM_PROMPT: Final[str] = """\
You are extracting structured fields from a raw job description. Be a
transformer, not an interpreter — only fill fields the source text directly
supports.

- company_name: the literal company name from the JD. If genuinely
  unparseable, return the role's apparent employer or "Unknown".
- company_domain: only fill if a company URL appears in the text.
- role_title: the title as written.
- seniority: infer from title + listed years-of-experience. "unknown" if
  ambiguous; do not default to "mid".
- must_have_skills / nice_to_have_skills: list verbatim from the JD's
  requirements sections. Distinguish required vs preferred ONLY if the JD
  uses that language. If a single skills section is present, put everything
  in must_have_skills.
- location: literal location string if present (e.g., "Warsaw, Poland" or
  "Remote (EU)").
- language: "pl" if the JD body is in Polish; "en" if English; "other"
  otherwise.
- raw_url: leave null unless a URL to the role itself appears in the JD.
- raw_text: echo back the input text unchanged.
"""


class JDTooShortError(ValueError):
    """Raised when the JD body is under MIN_JD_LENGTH characters."""


class JDParseError(RuntimeError):
    """Raised when ``messages.parse()`` returns no ``parsed_output`` despite a normal
    response (rare; usually indicates a refusal or a malformed response)."""


@dataclass
class ParsedJDResult:
    """Parser return value: the JD + telemetry."""

    jd: JobDescription
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


def parse_jd(
    raw_text: str,
    *,
    override_company: str | None = None,
    override_url: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> ParsedJDResult:
    """Parse ``raw_text`` into a ``JobDescription``.

    ``override_company`` and ``override_url`` are applied AFTER parsing so the
    LLM still sees the raw text intact — overrides correct the parsed result
    rather than coaching the model.
    """
    if len(raw_text.strip()) < MIN_JD_LENGTH:
        raise JDTooShortError(
            f"JD appears empty (< {MIN_JD_LENGTH} characters). Aborting before any API call."
        )

    if client is None:
        api_key = get_settings().anthropic_api_key
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to .env (copy from "
                ".env.example) before invoking the JD parser."
            )
        client = anthropic.Anthropic(api_key=api_key)

    log.info("resume.jd_parse.start", chars=len(raw_text))

    user_prompt = f"<job_description>\n{raw_text}\n</job_description>"

    response = client.messages.parse(
        model=JD_PARSER_MODEL,
        max_tokens=JD_PARSER_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": JD_PARSER_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        output_format=JobDescription,
    )

    parsed = response.parsed_output
    if parsed is None:
        raise JDParseError(
            "JD parser returned no parsed_output. This usually means the model "
            "refused or returned malformed JSON; rerun with --jd-text to retry."
        )

    if override_company:
        parsed = parsed.model_copy(update={"company_name": override_company})
    if override_url:
        parsed = parsed.model_copy(update={"raw_url": override_url})

    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cost = estimate_cost(
        model=JD_PARSER_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )

    log.info(
        "resume.jd_parse.done",
        company=parsed.company_name,
        role=parsed.role_title,
        seniority=parsed.seniority,
        language=parsed.language,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
    )

    return ParsedJDResult(
        jd=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        model=JD_PARSER_MODEL,
    )
