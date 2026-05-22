"""Tests for ``jmi.costs.estimate_cost`` arithmetic (PR-3.4)."""

from __future__ import annotations

import pytest

from jmi.costs import MODEL_PRICING, WEB_SEARCH_FEE_USD, estimate_cost


def test_opus_input_only() -> None:
    """1M input tokens on Opus 4.7 = $5.00."""
    assert estimate_cost(
        model="claude-opus-4-7", input_tokens=1_000_000, output_tokens=0
    ) == pytest.approx(5.0)


def test_opus_input_and_output() -> None:
    """3k input + 1.2k output on Opus 4.7 ≈ $0.045."""
    cost = estimate_cost(model="claude-opus-4-7", input_tokens=3_000, output_tokens=1_200)
    expected = (3_000 / 1_000_000) * 5.0 + (1_200 / 1_000_000) * 25.0
    assert cost == pytest.approx(round(expected, 4))


def test_sonnet_cheaper_than_opus_for_same_tokens() -> None:
    opus = estimate_cost(model="claude-opus-4-7", input_tokens=5000, output_tokens=1000)
    sonnet = estimate_cost(model="claude-sonnet-4-6", input_tokens=5000, output_tokens=1000)
    assert sonnet < opus


def test_cache_read_charged_at_reduced_rate() -> None:
    """5k cache-read tokens cost 10% of standard input rate on Opus 4.7."""
    cost = estimate_cost(
        model="claude-opus-4-7",
        input_tokens=5000,
        output_tokens=0,
        cache_read_tokens=5000,
    )
    expected = (5000 / 1_000_000) * MODEL_PRICING["claude-opus-4-7"]["cache_read"]
    assert cost == pytest.approx(round(expected, 4))


def test_cache_read_does_not_double_charge_input() -> None:
    """Cache-read tokens are subtracted from fresh-input billing."""
    only_cached = estimate_cost(
        model="claude-opus-4-7",
        input_tokens=5000,
        output_tokens=0,
        cache_read_tokens=5000,
    )
    only_fresh = estimate_cost(model="claude-opus-4-7", input_tokens=5000, output_tokens=0)
    assert only_cached < only_fresh


def test_web_search_fee_added() -> None:
    """3 searches = $0.030 on top of token cost."""
    base = estimate_cost(model="claude-opus-4-7", input_tokens=0, output_tokens=0)
    with_search = estimate_cost(
        model="claude-opus-4-7",
        input_tokens=0,
        output_tokens=0,
        web_search_requests=3,
    )
    assert with_search - base == pytest.approx(3 * WEB_SEARCH_FEE_USD)


def test_unknown_model_falls_back_to_opus_pricing() -> None:
    """Unknown model name returns the same cost as Opus 4.7."""
    unknown = estimate_cost(model="claude-future-100", input_tokens=1000, output_tokens=500)
    opus = estimate_cost(model="claude-opus-4-7", input_tokens=1000, output_tokens=500)
    assert unknown == pytest.approx(opus)


def test_haiku_pricing_in_table() -> None:
    assert "claude-haiku-4-5-20251001" in MODEL_PRICING
    assert MODEL_PRICING["claude-haiku-4-5-20251001"]["input"] == 1.0
