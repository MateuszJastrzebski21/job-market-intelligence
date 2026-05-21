"""Anthropic API cost estimation (PR-3.4).

Centralised pricing table so generators don't each carry their own constants.
Source: ``platform.claude.com/docs/en/about-claude/pricing`` (list prices as of
2026-05). When Anthropic changes prices, update this file and re-run the test
suite — `estimate_cost` is the single arithmetic chokepoint.
"""

from __future__ import annotations

from typing import Final, TypedDict


class _ModelPricing(TypedDict):
    input: float  # USD per million input tokens
    output: float  # USD per million output tokens
    cache_read: float  # USD per million cache-read tokens
    cache_write: float  # USD per million cache-write tokens


# USD per million tokens. Cache read is 0.10× input; cache write is 1.25× input.
MODEL_PRICING: Final[dict[str, _ModelPricing]] = {
    "claude-opus-4-7": {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.5,
        "cache_write": 6.25,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
}

# Anthropic web_search server tool: $10 per 1,000 searches.
WEB_SEARCH_FEE_USD: Final[float] = 0.010


def estimate_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    web_search_requests: int = 0,
) -> float:
    """USD estimate for one API call.

    Anthropic reports ``cache_read_input_tokens`` and
    ``cache_creation_input_tokens`` separately from ``input_tokens`` — pass
    each in its own argument. Cache-write tokens are charged at the write
    rate; cache-read at the read rate; the remainder of ``input_tokens`` at
    the full input rate.

    Unknown model: falls back to Opus pricing so cost estimates lean
    pessimistic. Returns USD rounded to 4 decimal places (cent-level
    precision is plenty for per-generation tracking).
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        pricing = MODEL_PRICING["claude-opus-4-7"]

    fresh_input = max(0, input_tokens - cache_read_tokens - cache_write_tokens)

    cost = 0.0
    cost += (fresh_input / 1_000_000) * pricing["input"]
    cost += (output_tokens / 1_000_000) * pricing["output"]
    cost += (cache_read_tokens / 1_000_000) * pricing["cache_read"]
    cost += (cache_write_tokens / 1_000_000) * pricing["cache_write"]
    cost += web_search_requests * WEB_SEARCH_FEE_USD

    return round(cost, 4)
