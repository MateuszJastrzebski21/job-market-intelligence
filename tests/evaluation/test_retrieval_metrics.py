"""Unit tests for the RAG retrieval metrics (audit H5 / E-1)."""

from __future__ import annotations

import math

import pytest

from jmi.evaluation.retrieval_metrics import (
    bootstrap_ci,
    mrr,
    ndcg,
    ndcg_at_k,
    ndcg_graded,
    paired_bootstrap_ci,
    recall_at_k,
)

# ---------- recall_at_k ----------


def test_recall_at_k_perfect() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=2) == 1.0


def test_recall_at_k_partial() -> None:
    # 1 of 2 relevant in top-2
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=2) == 0.5


def test_recall_at_k_zero() -> None:
    assert recall_at_k(["x", "y", "z"], {"a"}, k=2) == 0.0


def test_recall_at_k_k_larger_than_results() -> None:
    # Asking for top-5 but only 2 returned — still scored over what's there.
    assert recall_at_k(["a", "b"], {"a", "b", "c"}, k=5) == pytest.approx(2 / 3)


def test_recall_at_k_k_zero() -> None:
    assert recall_at_k(["a", "b"], {"a"}, k=0) == 0.0


def test_recall_at_k_empty_relevant_returns_one() -> None:
    """1.0 when nothing was supposed to be relevant — vacuously correct."""
    assert recall_at_k(["a", "b"], set(), k=5) == 1.0


def test_recall_at_k_empty_ranked() -> None:
    assert recall_at_k([], {"a"}, k=5) == 0.0


def test_recall_at_k_rejects_negative_k() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        recall_at_k(["a"], {"a"}, k=-1)


# ---------- mrr ----------


def test_mrr_first_hit_at_rank_one() -> None:
    assert mrr(["a", "b", "c"], {"a"}) == 1.0


def test_mrr_first_hit_at_rank_three() -> None:
    assert mrr(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_mrr_no_hit() -> None:
    assert mrr(["x", "y"], {"a"}) == 0.0


def test_mrr_empty_relevant() -> None:
    assert mrr(["a"], set()) == 0.0


def test_mrr_empty_ranked() -> None:
    assert mrr([], {"a"}) == 0.0


def test_mrr_picks_first_of_several_relevant() -> None:
    # b is at rank 2 even though c is also relevant at rank 3
    assert mrr(["x", "b", "c"], {"b", "c"}) == 0.5


# ---------- ndcg_at_k (binary) ----------


def test_ndcg_at_k_perfect_ranking() -> None:
    assert ndcg_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0


def test_ndcg_at_k_reverse_ranking() -> None:
    # Both relevant but ranked positions 1 and 2 vs ideal positions 1 and 2:
    # for binary, any ordering of the relevant set in top-k gives full DCG.
    assert ndcg_at_k(["b", "a"], {"a", "b"}, k=2) == 1.0


def test_ndcg_at_k_one_relevant_at_rank_one() -> None:
    # DCG = 1/log2(2) = 1; ideal DCG (one relevant at rank 1) = 1; → 1.0
    assert ndcg_at_k(["a", "x", "y"], {"a"}, k=3) == 1.0


def test_ndcg_at_k_one_relevant_at_rank_three() -> None:
    # DCG = 1/log2(4) = 0.5; ideal = 1; → 0.5
    assert ndcg_at_k(["x", "y", "a"], {"a"}, k=3) == pytest.approx(0.5)


def test_ndcg_at_k_empty_relevant_returns_one() -> None:
    assert ndcg_at_k(["a"], set(), k=5) == 1.0


def test_ndcg_at_k_rejects_negative_k() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ndcg_at_k(["a"], {"a"}, k=-1)


# ---------- ndcg_graded ----------


def test_ndcg_graded_perfect() -> None:
    relevance = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert ndcg_graded(["a", "b", "c"], relevance, k=3) == 1.0


def test_ndcg_graded_swapped_ranks_loses_score() -> None:
    relevance = {"a": 3.0, "b": 2.0}
    # ideal: 3/log2(2) + 2/log2(3) = 3.0 + 1.2618... = 4.2618...
    ideal = 3.0 + 2.0 / math.log2(3)
    # actual: 2/log2(2) + 3/log2(3)
    actual = 2.0 + 3.0 / math.log2(3)
    assert ndcg_graded(["b", "a"], relevance, k=2) == pytest.approx(actual / ideal)


def test_ndcg_graded_empty_relevance_returns_one() -> None:
    assert ndcg_graded(["a"], {}, k=5) == 1.0


def test_ndcg_graded_all_zero_grades_returns_one() -> None:
    assert ndcg_graded(["a"], {"a": 0.0}, k=1) == 1.0


def test_ndcg_alias_matches_ndcg_graded() -> None:
    """The legacy `ndcg` export (skeleton API) is now an alias of ndcg_graded."""
    relevance = {"a": 1.0, "b": 1.0}
    assert ndcg(["a", "b"], relevance, k=2) == ndcg_graded(["a", "b"], relevance, k=2)


# ---------- bootstrap_ci ----------


def test_bootstrap_ci_empty_returns_zero_pair() -> None:
    lo, hi = bootstrap_ci([])
    assert lo == 0.0
    assert hi == 0.0


def test_bootstrap_ci_single_value_is_point_mass() -> None:
    lo, hi = bootstrap_ci([0.5])
    assert lo == 0.5
    assert hi == 0.5


def test_bootstrap_ci_constant_values() -> None:
    # All values identical — CI collapses to that value.
    lo, hi = bootstrap_ci([0.7] * 20, seed=42)
    assert lo == pytest.approx(0.7)
    assert hi == pytest.approx(0.7)


def test_bootstrap_ci_brackets_mean() -> None:
    # CI on 15 values should bracket the sample mean for any reasonable seed.
    values = [0.0, 1.0, 0.5, 0.8, 0.2, 0.6, 0.4, 0.9, 0.3, 0.7, 0.5, 0.5, 1.0, 0.0, 0.6]
    mean = sum(values) / len(values)
    lo, hi = bootstrap_ci(values, seed=0, n_resamples=500)
    assert lo <= mean <= hi


def test_bootstrap_ci_deterministic_with_seed() -> None:
    values = [0.1, 0.4, 0.7, 0.9, 0.2]
    one = bootstrap_ci(values, seed=123)
    two = bootstrap_ci(values, seed=123)
    assert one == two


def test_bootstrap_ci_rejects_bad_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        bootstrap_ci([0.5], confidence=1.5)


def test_bootstrap_ci_rejects_zero_resamples() -> None:
    with pytest.raises(ValueError, match="n_resamples"):
        bootstrap_ci([0.5], n_resamples=0)


# ---------- paired_bootstrap_ci ----------


def test_paired_bootstrap_ci_identical_systems_zero_delta() -> None:
    values = [0.1, 0.4, 0.7, 0.9, 0.2]
    delta, lo, hi = paired_bootstrap_ci(values, values, seed=0)
    assert delta == 0.0
    assert lo == 0.0
    assert hi == 0.0


def test_paired_bootstrap_ci_a_strictly_better() -> None:
    # A scores 0.1 higher on every query — paired CI cleanly excludes zero.
    a = [0.6, 0.7, 0.8, 0.9, 0.5, 0.4, 0.7, 0.6, 0.8, 0.5]
    b = [0.5, 0.6, 0.7, 0.8, 0.4, 0.3, 0.6, 0.5, 0.7, 0.4]
    delta, lo, hi = paired_bootstrap_ci(a, b, seed=0, n_resamples=500)
    assert delta == pytest.approx(0.1)
    # Per-query delta is 0.1 everywhere — bootstrap of mean-delta is 0.1
    # almost surely.
    assert lo == pytest.approx(0.1)
    assert hi == pytest.approx(0.1)


def test_paired_bootstrap_ci_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        paired_bootstrap_ci([0.1, 0.2], [0.1])


def test_paired_bootstrap_ci_empty_returns_zeros() -> None:
    delta, lo, hi = paired_bootstrap_ci([], [])
    assert (delta, lo, hi) == (0.0, 0.0, 0.0)


def test_paired_bootstrap_ci_single_pair_is_point_mass() -> None:
    delta, lo, hi = paired_bootstrap_ci([0.8], [0.5])
    assert delta == pytest.approx(0.3)
    assert lo == pytest.approx(0.3)
    assert hi == pytest.approx(0.3)


def test_paired_bootstrap_ci_deterministic_with_seed() -> None:
    a = [0.5, 0.6, 0.4, 0.7, 0.5]
    b = [0.4, 0.5, 0.5, 0.6, 0.4]
    assert paired_bootstrap_ci(a, b, seed=7) == paired_bootstrap_ci(a, b, seed=7)
