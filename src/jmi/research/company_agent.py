"""Two-call company research agent (PR-3.4).

Call 1: Opus 4.7 + ``web_search_20250305`` tool. Claude decides when to search,
chains multiple queries server-side, and returns a prose research summary.

Call 2: Sonnet 4.6 + ``messages.parse(output_format=CompanyResearch)``. The
synthesis call is pure transformation — no web access. It reads Call 1's
prose and the extracted source URLs, then emits the structured schema.

The split avoids the under-tested ``tools=[web_search]`` + structured-outputs
combination (dossier §3 flags an analogous incompatibility for native
citations). The Sonnet 4.6 synthesis call adds ~$0.013 per generation —
worth it for reliability.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import anthropic
import structlog
from anthropic.types import ToolUnionParam

from jmi.config import get_settings
from jmi.costs import estimate_cost
from jmi.research.prompts import (
    RESEARCH_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from jmi.research.schemas import CompanyFact, CompanyResearch
from jmi.storage.company_research_cache import (
    CACHE_TTL_DAYS,
    CompanyResearchCacheRepository,
    CompanyResearchCacheRow,
)

log = structlog.get_logger(__name__)


class ResearchSynthesisError(RuntimeError):
    """Raised when Call 2 (``messages.parse``) returns no ``parsed_output``."""


WEB_SEARCH_TOOL_VERSION = "web_search_20250305"
DEFAULT_DEPTH = 3
RESEARCH_MODEL = "claude-opus-4-7"
SYNTHESIS_MODEL = "claude-sonnet-4-6"
RESEARCH_MAX_TOKENS = 2000
SYNTHESIS_MAX_TOKENS = 1500


def _web_search_tool(max_uses: int) -> dict[str, Any]:
    return {
        "type": WEB_SEARCH_TOOL_VERSION,
        "name": "web_search",
        "max_uses": max_uses,
    }


@dataclass
class ResearchResult:
    """Agent return value: the research + per-call telemetry."""

    research: CompanyResearch
    cache_hit: bool
    web_search_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int


@dataclass
class _Call1Result:
    final_text: str
    source_urls: list[str]
    web_search_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    degraded: bool
    degrade_reason: str | None


@dataclass
class _Call2Result:
    research: CompanyResearch
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CompanyResearchAgent:
    """Stateless across invocations (no instance state mutated by research_company).

    Holds the Anthropic client + cache repo. Inject ``client`` in tests with a
    ``FakeAnthropic`` that has separate queues for Call 1 (``messages.create``)
    and Call 2 (``messages.parse``).
    """

    def __init__(
        self,
        *,
        cache_repo: CompanyResearchCacheRepository,
        client: anthropic.Anthropic | None = None,
        research_model: str = RESEARCH_MODEL,
        synthesis_model: str = SYNTHESIS_MODEL,
    ) -> None:
        self._cache = cache_repo
        if client is None:
            api_key = get_settings().anthropic_api_key
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Add it to .env (copy from "
                    ".env.example) before invoking the company research agent."
                )
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self._research_model = research_model
        self._synthesis_model = synthesis_model

    def research_company(
        self,
        company_name: str,
        company_domain: str | None,
        *,
        depth: int = DEFAULT_DEPTH,
        use_cache: bool = True,
        ttl_days: int = CACHE_TTL_DAYS,
    ) -> ResearchResult:
        """Return ``CompanyResearch`` + telemetry.

        Cache hit: zero API calls. Cache miss: Call 1 → (if not degraded) Call 2.
        ``max_uses_exceeded`` on Call 1 short-circuits to a low-confidence
        fallback without invoking Call 2 and without caching the result (so
        the next attempt can retry).
        """
        key = self._cache.make_key(company_name, company_domain)
        if use_cache:
            cached = self._cache.get(key, ttl_days=ttl_days)
            if cached is not None:
                log.info("research.cache.hit", company=company_name, cache_key=key)
                return ResearchResult(
                    research=CompanyResearch.model_validate(cached.research_json),
                    cache_hit=True,
                    web_search_calls=0,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    duration_ms=0,
                )

        log.info("research.cache.miss", company=company_name)
        start = time.perf_counter()

        call1 = self._call_research(company_name, company_domain, depth=depth)
        if call1.degraded:
            duration_ms = int((time.perf_counter() - start) * 1000)
            research = _low_confidence_fallback(
                company_name, company_domain, reason=call1.degrade_reason or "unknown"
            )
            log.warning(
                "research.degraded",
                company=company_name,
                reason=call1.degrade_reason,
            )
            return ResearchResult(
                research=research,
                cache_hit=False,
                web_search_calls=call1.web_search_calls,
                input_tokens=call1.input_tokens,
                output_tokens=call1.output_tokens,
                cost_usd=call1.cost_usd,
                duration_ms=duration_ms,
            )

        call2 = self._call_synthesis(
            company_name,
            company_domain,
            research_text=call1.final_text,
            source_urls=call1.source_urls,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)

        self._cache.put(
            CompanyResearchCacheRow(
                key=key,
                company_name=company_name,
                company_domain=company_domain,
                research_json=call2.research.model_dump(mode="json"),
                fetched_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )

        log.info(
            "research.done",
            company=company_name,
            confidence=call2.research.confidence,
            web_search_calls=call1.web_search_calls,
            duration_ms=duration_ms,
        )

        return ResearchResult(
            research=call2.research,
            cache_hit=False,
            web_search_calls=call1.web_search_calls,
            input_tokens=call1.input_tokens + call2.input_tokens,
            output_tokens=call1.output_tokens + call2.output_tokens,
            cost_usd=call1.cost_usd + call2.cost_usd,
            duration_ms=duration_ms,
        )

    def _call_research(
        self, company_name: str, company_domain: str | None, *, depth: int
    ) -> _Call1Result:
        user_prompt = (
            f"Research {company_name}"
            + (f" (domain: {company_domain})" if company_domain else "")
            + ". Find recent news (last 90 days preferred), mission, tech stack "
            "signals, culture signals, hiring signals. Report sources for every "
            "claim."
        )

        # web_search_20250305 is a server tool; the SDK 0.96 type stubs do not
        # yet list it as a ToolUnionParam variant. Cast at the call site rather
        # than constructing a partial typed dict that won't match either union.
        tools = cast("list[ToolUnionParam]", [_web_search_tool(depth)])
        response = self._client.messages.create(
            model=self._research_model,
            max_tokens=RESEARCH_MAX_TOKENS,
            tools=tools,
            system=[
                {
                    "type": "text",
                    "text": RESEARCH_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )

        final_text, source_urls, degrade_reason = _parse_research_response(response)
        input_tokens, output_tokens, web_search_calls = _extract_research_usage(response)
        cost = estimate_cost(
            model=self._research_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            web_search_requests=web_search_calls,
        )

        return _Call1Result(
            final_text=final_text,
            source_urls=source_urls,
            web_search_calls=web_search_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            degraded=degrade_reason is not None,
            degrade_reason=degrade_reason,
        )

    def _call_synthesis(
        self,
        company_name: str,
        company_domain: str | None,
        *,
        research_text: str,
        source_urls: list[str],
    ) -> _Call2Result:
        urls_block = "\n".join(f"- {u}" for u in source_urls) if source_urls else "(none)"
        user_prompt = (
            f"Target company: {company_name}\n"
            f"Target domain: {company_domain or 'unknown'}\n\n"
            "<research_summary>\n"
            f"{research_text}\n"
            "</research_summary>\n\n"
            "<source_urls_observed>\n"
            f"{urls_block}\n"
            "</source_urls_observed>\n\n"
            "Extract the CompanyResearch schema strictly from the summary above."
        )

        response = self._client.messages.parse(
            model=self._synthesis_model,
            max_tokens=SYNTHESIS_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYNTHESIS_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
            output_format=CompanyResearch,
        )

        parsed = response.parsed_output
        if parsed is None:
            raise ResearchSynthesisError(
                "Research synthesis returned no parsed_output. This usually "
                "indicates the synthesis model returned malformed JSON; the "
                "agent will surface this as an exception so the caller can "
                "degrade to --no-research."
            )

        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cost = estimate_cost(
            model=self._synthesis_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

        return _Call2Result(
            research=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


def _parse_research_response(response: Any) -> tuple[str, list[str], str | None]:
    """Extract the final text, observed source URLs, and any degrade reason.

    Returns ``(final_text, source_urls, degrade_reason)``. ``degrade_reason``
    is set to a non-None string when the response indicates a
    ``max_uses_exceeded`` or similar error in a web_search_tool_result block.
    """
    final_texts: list[str] = []
    source_urls: list[str] = []
    degrade_reason: str | None = None

    for block in getattr(response, "content", []):
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_val = getattr(block, "text", "")
            if text_val:
                final_texts.append(text_val)
        elif block_type == "web_search_tool_result":
            content = getattr(block, "content", None)
            if isinstance(content, dict):
                # Error block shape: {"type": "web_search_tool_result_error", "error_code": "..."}
                if content.get("type") == "web_search_tool_result_error":
                    degrade_reason = content.get("error_code", "web_search_error")
            elif isinstance(content, list):
                for result in content:
                    url = (
                        result.get("url")
                        if isinstance(result, dict)
                        else getattr(result, "url", None)
                    )
                    if url and url not in source_urls:
                        source_urls.append(url)

    return ("\n\n".join(final_texts), source_urls, degrade_reason)


def _extract_research_usage(response: Any) -> tuple[int, int, int]:
    """Return ``(input_tokens, output_tokens, web_search_calls)``."""
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0

    web_search_calls = 0
    server_tool_use = getattr(usage, "server_tool_use", None)
    if isinstance(server_tool_use, dict):
        web_search_calls = int(server_tool_use.get("web_search_requests", 0) or 0)
    elif server_tool_use is not None:
        web_search_calls = int(getattr(server_tool_use, "web_search_requests", 0) or 0)

    return (input_tokens, output_tokens, web_search_calls)


def _low_confidence_fallback(
    company_name: str, company_domain: str | None, *, reason: str
) -> CompanyResearch:
    """Build a minimally-populated low-confidence ``CompanyResearch``.

    Triggered by ``max_uses_exceeded`` or other Call 1 degradation. The cover
    letter generator branches on ``confidence == 'low'`` to skip the
    company-specific opener and fall back to a role-specific generic opener.
    """
    summary = f"{company_name} — research degraded ({reason}); using generic opener."
    return CompanyResearch(
        company_name=company_name,
        one_line_summary=summary,
        mission_or_thesis=None,
        recent_news=[],
        tech_stack_signals=[],
        culture_signals=[],
        hiring_signals=[],
        specific_opener_candidates=[],
        confidence="low",
        search_queries_used=[],
        notes=f"degrade_reason={reason}",
    )


# Re-export so callers can build their own fallbacks without reaching into
# private names.
low_confidence_fallback = _low_confidence_fallback


__all__ = [
    "CompanyResearchAgent",
    "ResearchResult",
    "WEB_SEARCH_TOOL_VERSION",
    "DEFAULT_DEPTH",
    "RESEARCH_MODEL",
    "SYNTHESIS_MODEL",
    "low_confidence_fallback",
    "CompanyFact",
]
