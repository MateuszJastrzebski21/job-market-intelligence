"""Tests for ``CompanyResearchAgent`` two-call architecture (PR-3.4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import anthropic
from sqlalchemy.orm import Session

from jmi.research.company_agent import (
    DEFAULT_DEPTH,
    RESEARCH_MODEL,
    SYNTHESIS_MODEL,
    WEB_SEARCH_TOOL_VERSION,
    CompanyResearchAgent,
)
from jmi.research.schemas import CompanyFact, CompanyResearch
from jmi.storage.company_research_cache import (
    CompanyResearchCacheRepository,
    CompanyResearchCacheRow,
)
from tests.fixtures.anthropic_responses import (
    FakeAnthropic,
    FakeWebSearchResultItem,
    build_max_uses_exceeded_message,
    build_parsed_message,
    build_web_search_message,
)


def _sample_research(*, confidence: str = "high") -> CompanyResearch:
    return CompanyResearch(
        company_name="Acme",
        one_line_summary="Acme builds AI agents.",
        mission_or_thesis=CompanyFact(
            fact="Mission: agents that work.",
            source_url="https://acme.com/about",
            recency_estimate="last_90d",
        ),
        recent_news=[
            CompanyFact(
                fact="Launched Vertex AI thing.",
                source_url="https://news.example.com/acme",
                recency_estimate="last_30d",
            )
        ],
        tech_stack_signals=[
            CompanyFact(
                fact="Uses pgvector.",
                source_url="https://acme.com/eng",
                recency_estimate="last_90d",
            )
        ],
        specific_opener_candidates=["I read about your Vertex launch..."],
        confidence=cast(Any, confidence),
        search_queries_used=["Acme recent news"],
    )


def _make_agent(
    db_session: Session, fake: FakeAnthropic
) -> tuple[CompanyResearchAgent, CompanyResearchCacheRepository]:
    cache = CompanyResearchCacheRepository(db_session)
    agent = CompanyResearchAgent(
        cache_repo=cache,
        client=cast(anthropic.Anthropic, fake),
    )
    return agent, cache


def test_cache_hit_skips_api_calls(db_session: Session) -> None:
    cache = CompanyResearchCacheRepository(db_session)
    key = cache.make_key("Acme", "acme.com")
    research = _sample_research()
    cache.put(
        CompanyResearchCacheRow(
            key=key,
            company_name="Acme",
            company_domain="acme.com",
            research_json=research.model_dump(mode="json"),
            fetched_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )

    fake = FakeAnthropic()  # no responses queued — proves no API call
    agent = CompanyResearchAgent(cache_repo=cache, client=cast(anthropic.Anthropic, fake))
    result = agent.research_company("Acme", "acme.com")

    assert result.cache_hit is True
    assert result.web_search_calls == 0
    assert result.cost_usd == 0.0
    assert result.research.company_name == "Acme"
    assert fake.messages.recorded_create_calls == []
    assert fake.messages.recorded_parse_calls == []


def test_cache_miss_runs_two_calls(db_session: Session) -> None:
    research = _sample_research()
    call1 = build_web_search_message(
        queries=["Acme recent news"],
        results=[
            FakeWebSearchResultItem(
                title="Acme launch",
                url="https://news.example.com/acme",
                page_age="2026-04-30",
            )
        ],
        final_text="Acme launched Vertex thing. (source: https://news.example.com/acme)",
        web_search_requests=1,
    )
    call2 = build_parsed_message(research)
    fake = FakeAnthropic(create_responses=[call1], parse_responses=[call2])
    agent, cache = _make_agent(db_session, fake)

    result = agent.research_company("Acme", "acme.com")

    assert result.cache_hit is False
    assert result.web_search_calls == 1
    assert result.research.confidence == "high"
    assert result.input_tokens > 0
    assert result.cost_usd > 0
    # Cache now holds the result
    fetched = cache.get(cache.make_key("Acme", "acme.com"))
    assert fetched is not None


def test_call1_uses_web_search_tool_with_depth(db_session: Session) -> None:
    research = _sample_research()
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(
                queries=["x"], results=[], final_text="ok", web_search_requests=0
            )
        ],
        parse_responses=[build_parsed_message(research)],
    )
    agent, _ = _make_agent(db_session, fake)

    agent.research_company("Acme", None, depth=5)

    call1_kwargs = fake.messages.recorded_create_calls[0]
    assert call1_kwargs["model"] == RESEARCH_MODEL
    tools = call1_kwargs["tools"]
    assert tools == [{"type": WEB_SEARCH_TOOL_VERSION, "name": "web_search", "max_uses": 5}]


def test_call2_uses_synthesis_model_and_output_format(db_session: Session) -> None:
    research = _sample_research()
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(
                queries=["x"],
                results=[FakeWebSearchResultItem(url="https://acme.com")],
                final_text="summary",
                web_search_requests=1,
            )
        ],
        parse_responses=[build_parsed_message(research)],
    )
    agent, _ = _make_agent(db_session, fake)

    agent.research_company("Acme", "acme.com")

    call2_kwargs = fake.messages.recorded_parse_calls[0]
    assert call2_kwargs["model"] == SYNTHESIS_MODEL
    assert call2_kwargs["output_format"] is CompanyResearch
    # Source URL threaded through into Call 2 prompt:
    assert "https://acme.com" in call2_kwargs["messages"][0]["content"]


def test_call1_system_prompt_has_cache_control(db_session: Session) -> None:
    research = _sample_research()
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(queries=[], results=[], final_text="ok", web_search_requests=0)
        ],
        parse_responses=[build_parsed_message(research)],
    )
    agent, _ = _make_agent(db_session, fake)

    agent.research_company("Acme", None)

    system = fake.messages.recorded_create_calls[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_max_uses_exceeded_short_circuits_to_low_confidence(db_session: Session) -> None:
    fake = FakeAnthropic(
        create_responses=[build_max_uses_exceeded_message()],
        parse_responses=[],  # Call 2 must not happen
    )
    agent, cache = _make_agent(db_session, fake)

    result = agent.research_company("Obscure", None)

    assert result.cache_hit is False
    assert result.research.confidence == "low"
    assert result.research.specific_opener_candidates == []
    assert "max_uses_exceeded" in (result.research.notes or "")
    assert fake.messages.recorded_parse_calls == []
    # Low-confidence fallback is NOT cached so the next attempt can retry:
    assert cache.get(cache.make_key("Obscure", None)) is None


def test_default_depth_is_three(db_session: Session) -> None:
    assert DEFAULT_DEPTH == 3
    research = _sample_research()
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(queries=[], results=[], final_text="ok", web_search_requests=0)
        ],
        parse_responses=[build_parsed_message(research)],
    )
    agent, _ = _make_agent(db_session, fake)
    agent.research_company("Acme", None)
    tools = fake.messages.recorded_create_calls[0]["tools"]
    assert tools[0]["max_uses"] == 3


def test_expired_cache_triggers_refresh(db_session: Session) -> None:
    cache = CompanyResearchCacheRepository(db_session)
    key = cache.make_key("Acme", "acme.com")
    expired_research = _sample_research(confidence="medium")
    cache.put(
        CompanyResearchCacheRow(
            key=key,
            company_name="Acme",
            company_domain="acme.com",
            research_json=expired_research.model_dump(mode="json"),
            fetched_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10),
        )
    )

    fresh_research = _sample_research(confidence="high")
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(
                queries=["q"],
                results=[FakeWebSearchResultItem(url="https://a")],
                final_text="ok",
                web_search_requests=1,
            )
        ],
        parse_responses=[build_parsed_message(fresh_research)],
    )
    agent = CompanyResearchAgent(cache_repo=cache, client=cast(anthropic.Anthropic, fake))

    result = agent.research_company("Acme", "acme.com")

    assert result.cache_hit is False
    assert result.research.confidence == "high"


def test_use_cache_false_forces_refresh(db_session: Session) -> None:
    cache = CompanyResearchCacheRepository(db_session)
    key = cache.make_key("Acme", "acme.com")
    cached_research = _sample_research(confidence="medium")
    cache.put(
        CompanyResearchCacheRow(
            key=key,
            company_name="Acme",
            company_domain="acme.com",
            research_json=cached_research.model_dump(mode="json"),
            fetched_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    fresh_research = _sample_research(confidence="high")
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(
                queries=["q"],
                results=[FakeWebSearchResultItem(url="https://a")],
                final_text="ok",
                web_search_requests=1,
            )
        ],
        parse_responses=[build_parsed_message(fresh_research)],
    )
    agent = CompanyResearchAgent(cache_repo=cache, client=cast(anthropic.Anthropic, fake))

    result = agent.research_company("Acme", "acme.com", use_cache=False)

    assert result.cache_hit is False
    assert result.research.confidence == "high"


def test_source_urls_deduplicated_across_results(db_session: Session) -> None:
    research = _sample_research()
    same_url = FakeWebSearchResultItem(url="https://same.com/page")
    fake = FakeAnthropic(
        create_responses=[
            build_web_search_message(
                queries=["a", "b"],
                results=[same_url, same_url],
                final_text="ok",
                web_search_requests=2,
            )
        ],
        parse_responses=[build_parsed_message(research)],
    )
    agent, _ = _make_agent(db_session, fake)
    agent.research_company("Acme", None)

    call2_prompt = fake.messages.recorded_parse_calls[0]["messages"][0]["content"]
    # The URL should appear exactly once in the source-urls block.
    assert call2_prompt.count("- https://same.com/page") == 1
