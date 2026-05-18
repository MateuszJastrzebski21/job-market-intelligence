from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import anthropic
import structlog
from pydantic import ValidationError

from jmi.config import get_settings
from jmi.extractors.prompt import build_system_prompt, format_user_message
from jmi.extractors.schema import JobExtractSchema
from jmi.models.job import JobExtract, JobPosting
from jmi.storage.jobs import JobExtractRepository, JobPostingRepository

log = structlog.get_logger(__name__)

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096

# A response is only trustworthy when the model finished normally. Any other
# stop_reason (notably "refusal") means parsed_output may be non-conforming.
_VALID_STOP_REASONS = frozenset({"end_turn", "stop_sequence"})


class _RefusalError(Exception):
    """Raised when a response stopped for a reason other than normal completion
    (e.g. a refusal); its parsed_output must not be persisted. See ADR-0005."""

    def __init__(self, stop_reason: str | None) -> None:
        self.stop_reason = stop_reason
        super().__init__(f"untrustworthy stop_reason: {stop_reason!r}")


@dataclass
class ExtractStats:
    inserted: int = 0
    skipped: int = 0
    invalid: int = 0
    refused: int = 0
    failed_api_calls: int = 0
    cached_hits: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0


class AnthropicExtractor:
    """Run LLM extraction on JobPostings. One posting = one `messages.parse()`
    call. Adds frozen-prefix prompt caching via `cache_control` on the system
    block. See ADR-0005 (why `parse()`) and ADR-0006 (why separated pipeline)."""

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
                    "ANTHROPIC_API_KEY is not set. Add it to .env "
                    "(copy from .env.example) before running `jmi extract`."
                )
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self.model = model
        self._max_tokens = max_tokens
        self._system_prompt = build_system_prompt()

    def extract_one(self, posting: JobPosting) -> JobExtract:
        user_content = format_user_message(
            title=posting.title,
            company_name=posting.company_name,
            location=posting.location_raw,
            description_text=posting.description_text,
        )

        response = self._client.messages.parse(
            model=self.model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
            output_format=JobExtractSchema,
        )

        if response.stop_reason not in _VALID_STOP_REASONS:
            raise _RefusalError(response.stop_reason)

        parsed: JobExtractSchema = response.parsed_output

        return JobExtract(
            job_posting_id=posting.id,
            seniority=parsed.seniority,
            tech_stack=parsed.tech_stack,
            salary_min=parsed.salary_min,
            salary_max=parsed.salary_max,
            salary_currency=parsed.salary_currency,
            remote_policy=parsed.remote_policy,
            years_experience_min=parsed.years_experience_min,
            employment_type=parsed.employment_type,
            model_name=self.model,
            # warnings="none": SDK 0.96 wraps content blocks in ParsedTextBlock[TypeVar]
            # subclasses which aren't in the static content Union — the dump is correct,
            # the warnings are noise.
            raw_llm_response=response.model_dump(mode="json", warnings="none"),
            extracted_at=datetime.now(tz=UTC),
        )

    def run(
        self,
        posting_repo: JobPostingRepository,
        extract_repo: JobExtractRepository,
        *,
        limit: int | None = None,
    ) -> ExtractStats:
        stats = ExtractStats()
        postings = posting_repo.list(limit=limit or 1000)

        for posting in postings:
            if not posting.description_text:
                log.info(
                    "extract.skip.no_description",
                    source=posting.source,
                    posting_id=str(posting.id),
                )
                stats.skipped += 1
                continue

            existing = extract_repo.get_by_posting_and_model(posting.id, self.model)
            if existing is not None:
                stats.skipped += 1
                continue

            try:
                extract = self.extract_one(posting)
            except ValidationError as exc:
                log.warning(
                    "extract.skip.invalid",
                    source=posting.source,
                    posting_id=str(posting.id),
                    model=self.model,
                    errors=exc.errors(),
                )
                stats.invalid += 1
                continue
            except _RefusalError as exc:
                log.warning(
                    "extract.refused",
                    source=posting.source,
                    posting_id=str(posting.id),
                    model=self.model,
                    stop_reason=exc.stop_reason,
                )
                stats.refused += 1
                continue
            except anthropic.APIError as exc:
                log.error(
                    "extract.skip.api_error",
                    source=posting.source,
                    posting_id=str(posting.id),
                    model=self.model,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
                stats.failed_api_calls += 1
                continue

            _update_stats(stats, extract)
            extract_repo.add(extract)
            stats.inserted += 1

        log.info(
            "extract.done",
            model=self.model,
            inserted=stats.inserted,
            skipped=stats.skipped,
            invalid=stats.invalid,
            refused=stats.refused,
            failed_api_calls=stats.failed_api_calls,
            cached_hits=stats.cached_hits,
            total_input_tokens=stats.total_input_tokens,
            total_output_tokens=stats.total_output_tokens,
            total_cache_read_tokens=stats.total_cache_read_tokens,
        )
        return stats


def _update_stats(stats: ExtractStats, extract: JobExtract) -> None:
    """Pull usage metrics out of the stored raw_llm_response and accumulate."""
    usage = extract.raw_llm_response.get("usage") or {}
    input_tokens = usage.get("input_tokens") or 0
    output_tokens = usage.get("output_tokens") or 0
    cache_read = usage.get("cache_read_input_tokens") or 0
    cache_creation = usage.get("cache_creation_input_tokens") or 0

    stats.total_input_tokens += input_tokens
    stats.total_output_tokens += output_tokens
    stats.total_cache_read_tokens += cache_read
    stats.total_cache_creation_tokens += cache_creation
    if cache_read > 0:
        stats.cached_hits += 1
