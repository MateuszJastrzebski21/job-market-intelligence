"""Ranking metrics for Phase 3 retrieval evaluation (audit H5 / E-1).

SKELETON — signatures and contracts only. The implementations land in PR-3.2
with the custom RAG retriever and its deterministic embedding fixtures. These
are pure functions over (ranked ids, relevant ids): no DB, no embedding model,
so they unit-test trivially, mirroring the existing extraction-metrics module.
"""

from collections.abc import Sequence


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of `relevant_ids` present in the top `k` of `ranked_ids`.

    `ranked_ids` is the retriever's output, best-ranked first; `relevant_ids`
    is the golden set. Returns recall in [0.0, 1.0] — 1.0 when `relevant_ids`
    is empty.
    """
    raise NotImplementedError("recall_at_k lands in PR-3.2 with the RAG retriever")


def mrr(ranked_ids: Sequence[str], relevant_ids: set[str]) -> float:
    """Mean reciprocal rank — 1 / rank of the first relevant id in `ranked_ids`.

    Rank counts from 1; returns 0.0 when no id in `ranked_ids` is relevant.
    """
    raise NotImplementedError("mrr lands in PR-3.2 with the RAG retriever")


def ndcg(ranked_ids: Sequence[str], relevance: dict[str, float], k: int) -> float:
    """Normalised discounted cumulative gain over the top `k` of `ranked_ids`.

    `relevance` maps a chunk id to its graded relevance; ids absent from the
    map score 0. Returns nDCG in [0.0, 1.0] — the DCG of `ranked_ids` divided
    by the ideal DCG.
    """
    raise NotImplementedError("ndcg lands in PR-3.2 with the RAG retriever")
