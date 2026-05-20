"""Ranking metrics for Phase 3 retrieval evaluation (audit H5 / E-1).

Pure functions over `(ranked ids, relevant ids)` — no DB, no embedding model,
so unit tests stay deterministic and offline (E-3). Mirrors the structure of
`metrics.py` (extraction metrics).

PR-3.2 implementation. The skeletons in the prior revision raised
`NotImplementedError`; this revision implements them per the dossier (§3 of
`docs/research/pr-3.2-rag-comparison-dossier.md`):

- `recall_at_k`, `mrr`, `ndcg_at_k` are the headline metrics. nDCG accepts
  graded relevance via the `relevance` map; the seed schema's "binary for v1"
  decision means callers usually pass `{id: 1.0 for id in relevant_ids}`.
- `bootstrap_ci` returns a percentile bootstrap CI — bounded metrics that
  skew near 0/1 misbehave under a normal approximation (Efron 1979).
- `paired_bootstrap_ci` resamples query indices ONCE and scores both systems
  on the same draw, so per-query difficulty cancels out — the tight CI on
  the *difference* is the honest comparison at N≈15.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of `relevant_ids` present in the top `k` of `ranked_ids`.

    `ranked_ids` is the retriever's output, best-ranked first. Returns
    recall in [0.0, 1.0]; 1.0 when `relevant_ids` is empty (the retriever
    correctly produced no false positives among the relevant set).
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    if not relevant_ids:
        return 1.0
    top_k = set(ranked_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def mrr(ranked_ids: Sequence[str], relevant_ids: set[str]) -> float:
    """Mean reciprocal rank — 1 / rank of the first relevant id in `ranked_ids`.

    Rank counts from 1. Returns 0.0 when no id in `ranked_ids` is relevant
    (and when `ranked_ids` is empty). Returns 0.0 when `relevant_ids` is
    empty — there is nothing to rank against, so there is no reciprocal.
    """
    if not relevant_ids:
        return 0.0
    for position, cid in enumerate(ranked_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    """Binary nDCG@k — `recall@k`'s rank-sensitive cousin.

    Treats each id in `relevant_ids` as relevance 1, every other id as 0.
    Returns `DCG@k / IDCG@k` in [0.0, 1.0]; 1.0 when `relevant_ids` is empty
    (consistent with `recall_at_k`) or when the ranking is ideal.

    See `ndcg_graded` for the non-binary variant used when callers have a
    proper graded-relevance map (the seed schema's `graded_relevance` field).
    """
    relevance: dict[str, float] = {cid: 1.0 for cid in relevant_ids}
    return ndcg_graded(ranked_ids, relevance, k)


def ndcg_graded(ranked_ids: Sequence[str], relevance: dict[str, float], k: int) -> float:
    """Normalised discounted cumulative gain over the top `k` of `ranked_ids`.

    `relevance` maps a chunk id to its graded relevance; ids absent from the
    map score 0. Returns nDCG in [0.0, 1.0] — the DCG of `ranked_ids` divided
    by the ideal DCG. Returns 1.0 when `relevance` is empty or contains no
    positive grades (the ideal DCG is 0; conventionally nDCG is then 1.0).
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    dcg = _dcg(ranked_ids, relevance, k)
    ideal_ranking = sorted(relevance.values(), reverse=True)
    idcg = _dcg_from_grades(ideal_ranking, k)
    if idcg == 0.0:
        return 1.0
    return dcg / idcg


def _dcg(ranked_ids: Sequence[str], relevance: dict[str, float], k: int) -> float:
    grades = [relevance.get(cid, 0.0) for cid in ranked_ids[:k]]
    return _dcg_from_grades(grades, k)


def _dcg_from_grades(grades: Sequence[float], k: int) -> float:
    total = 0.0
    for position, grade in enumerate(grades[:k], start=1):
        total += grade / math.log2(position + 1)
    return total


def bootstrap_ci(
    values: Sequence[float],
    confidence: float = 0.95,
    n_resamples: int = 1000,
    seed: int | None = None,
) -> tuple[float, float]:
    """Percentile bootstrap CI on the mean of `values`.

    Resamples `values` with replacement `n_resamples` times, takes each
    resample's mean, returns the (lo, hi) percentiles framing `confidence`.
    Default 95% CI; pass `seed` for deterministic tests.

    Empty input returns `(0.0, 0.0)` — there is no mean to bound. Single-value
    input returns `(value, value)`.

    Resamples the supplied values directly. To compare two systems on the
    same queries, use `paired_bootstrap_ci` so per-query difficulty cancels
    (dossier §3).
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1, got {n_resamples}")
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return float(values[0]), float(values[0])

    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_index = max(0, int(alpha * n_resamples))
    hi_index = min(n_resamples - 1, int((1.0 - alpha) * n_resamples))
    return means[lo_index], means[hi_index]


def paired_bootstrap_ci(
    values_a: Sequence[float],
    values_b: Sequence[float],
    confidence: float = 0.95,
    n_resamples: int = 1000,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """Paired bootstrap CI on the per-query mean difference `a - b`.

    Both systems must be scored on the same queries in the same order —
    index `i` of `values_a` and `values_b` is the same query. Resamples
    query indices once per iteration, scores both systems on the resampled
    indices, takes the difference of means. Returns `(mean_delta, lo, hi)`.

    Tighter CI than either system's own bootstrap because per-query
    difficulty cancels (Efron 1979 → dossier §3 application). At N≈15 this
    is the only honest way to claim "system A beats system B."
    """
    if len(values_a) != len(values_b):
        raise ValueError(
            f"values_a and values_b must be the same length; got {len(values_a)} vs {len(values_b)}"
        )
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1, got {n_resamples}")
    n = len(values_a)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean_delta = sum(a - b for a, b in zip(values_a, values_b, strict=True)) / n
    if n == 1:
        return mean_delta, mean_delta, mean_delta

    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(n_resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        mean_a = sum(values_a[i] for i in indices) / n
        mean_b = sum(values_b[i] for i in indices) / n
        deltas.append(mean_a - mean_b)
    deltas.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_index = max(0, int(alpha * n_resamples))
    hi_index = min(n_resamples - 1, int((1.0 - alpha) * n_resamples))
    return mean_delta, deltas[lo_index], deltas[hi_index]


# ---------- Backward-compat shim ----------
# Skeleton revision exported `ndcg(ranked, relevance, k)` taking a graded map.
# Keep that name as an alias so existing imports do not break.
ndcg = ndcg_graded
