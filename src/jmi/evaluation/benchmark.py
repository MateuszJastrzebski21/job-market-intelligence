"""Retrieval benchmark harness — scores any pipeline against the ground-truth seed.

The benchmark depends on a structural protocol (`RetrievalPipeline`) so it does
NOT import worktree A's or worktree B's pipeline modules — those modules do not
live on the worktree C branch. Adapter helpers (`make_chunk_id_resolver`,
`adapt_scored_chunks`) translate either side's `ScoredChunk` shape into the
canonical `{achievement_key}::{section}` ids the seed file uses. A `StubPipeline`
is provided for tests so this module remains importable on the C branch alone.

Runtime composition (worktree A or B):

    pipeline = SomeRagPipeline(...)        # the real one
    resolver = make_chunk_id_resolver(session)
    adapter = ScoredChunkAdapter(pipeline, resolver, name="custom-rerank")
    result = benchmark_pipeline(adapter, seed, k=5)

The harness writes structured logs (no chunk text — S-2) for the per-stage
timing constraint (O-1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from jmi.db.models import AchievementORM
from jmi.evaluation.retrieval_metrics import (
    bootstrap_ci,
    mrr,
    ndcg_at_k,
    paired_bootstrap_ci,
    recall_at_k,
)
from jmi.evaluation.retrieval_seed import (
    RagSeedEntry,
    RagSeedFile,
    chunk_id_for,
    load_seed,
)

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)

SECTION_ORDER: tuple[str, ...] = ("context", "approach", "impact", "lessons")


# ---------- Pipeline protocol ----------


class RetrievalPipeline(Protocol):
    """The structural shape the benchmark depends on.

    Implementations must return canonical chunk ids (`{stem}::{section}`) in
    ranked order, best-first. Both worktree A's and worktree B's RagPipeline
    classes return `ScoredChunk` objects; `ScoredChunkAdapter` wraps either to
    satisfy this protocol.
    """

    name: str

    def retrieve_chunk_ids(self, query: str, k: int = 5) -> list[str]: ...


# ---------- Adapter: ScoredChunk → canonical chunk ids ----------


def make_chunk_id_resolver(session: Session) -> Callable[[UUID, int], str]:
    """Return a closure that maps `(achievement_id, chunk_index) -> canonical id`.

    Reads every achievement's `source_path` once at construction so the closure
    is O(1) per lookup. Both worktree A's and worktree B's chunkers use the
    same fixed `SECTION_ORDER` (context, approach, impact, lessons); the
    closure asserts `0 <= chunk_index < 4` and indexes that tuple.
    """
    rows = session.execute(select(AchievementORM.id, AchievementORM.source_path)).all()
    by_id: dict[UUID, str] = {row[0]: row[1] for row in rows}

    def resolver(achievement_id: UUID, chunk_index: int) -> str:
        if achievement_id not in by_id:
            raise LookupError(f"achievement_id {achievement_id} not in DB; cannot resolve chunk id")
        if not 0 <= chunk_index < len(SECTION_ORDER):
            raise ValueError(f"chunk_index {chunk_index} out of range [0, {len(SECTION_ORDER)})")
        section = SECTION_ORDER[chunk_index]
        return chunk_id_for(by_id[achievement_id], section)

    return resolver


class _ScoredChunkLike(Protocol):
    """Structural shape of both worktree A's and worktree B's ScoredChunk."""

    achievement_id: UUID
    chunk_index: int


class ScoredChunkAdapter:
    """Wrap a real RagPipeline so it satisfies `RetrievalPipeline`.

    `inner` is either worktree A's RagPipeline or worktree B's — anything with
    a callable that returns a list of `ScoredChunk`-shaped objects. The caller
    supplies `retrieve_fn` because A's signature is `(session, query, k)` and
    B's is `(query, k, rerank)`; binding it here keeps the adapter ignorant of
    each side's wiring quirks.
    """

    def __init__(
        self,
        name: str,
        retrieve_fn: Callable[[str, int], Sequence[_ScoredChunkLike]],
        resolver: Callable[[UUID, int], str],
    ) -> None:
        self.name = name
        self._retrieve_fn = retrieve_fn
        self._resolver = resolver

    def retrieve_chunk_ids(self, query: str, k: int = 5) -> list[str]:
        chunks = self._retrieve_fn(query, k)
        return [self._resolver(c.achievement_id, c.chunk_index) for c in chunks]


# ---------- StubPipeline (for tests on C alone) ----------


class StubPipeline:
    """A deterministic, dependency-free RetrievalPipeline for unit tests.

    Each query string is looked up in `answers` to retrieve a precomputed list
    of canonical chunk ids. Useful for testing the harness without spinning up
    a DB, an embedder, or a real retriever.
    """

    def __init__(self, name: str, answers: dict[str, list[str]]) -> None:
        self.name = name
        self._answers = answers

    def retrieve_chunk_ids(self, query: str, k: int = 5) -> list[str]:
        return list(self._answers.get(query, []))[:k]


# ---------- Result models ----------


class QueryResult(BaseModel):
    """Per-query benchmark result row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str
    query: str
    query_language: str
    relevant_chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    recall_at_k: float
    mrr: float
    ndcg_at_k: float


class MetricSummary(BaseModel):
    """Aggregate metric with bootstrap CI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mean: float
    ci_lo: float
    ci_hi: float

    @classmethod
    def from_values(
        cls, values: Sequence[float], confidence: float = 0.95, seed: int = 42
    ) -> MetricSummary:
        if not values:
            return cls(mean=0.0, ci_lo=0.0, ci_hi=0.0)
        mean = sum(values) / len(values)
        lo, hi = bootstrap_ci(values, confidence=confidence, seed=seed)
        return cls(mean=mean, ci_lo=lo, ci_hi=hi)


class BenchmarkResult(BaseModel):
    """One benchmark run — one pipeline against one seed at one k."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_name: str
    config: dict[str, Any]
    k: int
    seed_version: str
    seed_file: str | None
    timestamp: datetime
    per_query: list[QueryResult]
    recall: MetricSummary
    mrr: MetricSummary
    ndcg: MetricSummary

    def recall_values(self) -> list[float]:
        return [q.recall_at_k for q in self.per_query]

    def mrr_values(self) -> list[float]:
        return [q.mrr for q in self.per_query]

    def ndcg_values(self) -> list[float]:
        return [q.ndcg_at_k for q in self.per_query]


# ---------- Core benchmark function ----------


def _score_query(entry: RagSeedEntry, retrieved: list[str], k: int) -> QueryResult:
    relevant_set = set(entry.relevant_chunk_ids)
    return QueryResult(
        query_id=entry.id,
        query=entry.query,
        query_language=entry.query_language,
        relevant_chunk_ids=list(entry.relevant_chunk_ids),
        retrieved_chunk_ids=retrieved,
        recall_at_k=recall_at_k(retrieved, relevant_set, k),
        mrr=mrr(retrieved, relevant_set),
        ndcg_at_k=ndcg_at_k(retrieved, relevant_set, k),
    )


def benchmark_pipeline(
    pipeline: RetrievalPipeline,
    seed: RagSeedFile,
    k: int = 5,
    config: dict[str, Any] | None = None,
    bootstrap_seed: int = 42,
    seed_file_path: str | Path | None = None,
) -> BenchmarkResult:
    """Score `pipeline` against every entry in `seed`. Returns a `BenchmarkResult`.

    Per-query metrics are computed in order so a downstream comparison
    (paired bootstrap) can resample query indices on aligned vectors.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    per_query: list[QueryResult] = []
    log.info(
        "rag.benchmark.start",
        pipeline=pipeline.name,
        k=k,
        n_queries=len(seed.entries),
    )
    for entry in seed.entries:
        retrieved = pipeline.retrieve_chunk_ids(entry.query, k=k)
        per_query.append(_score_query(entry, retrieved, k))
        log.info(
            "rag.benchmark.query",
            pipeline=pipeline.name,
            query_id=entry.id,
            n_retrieved=len(retrieved),
            recall_at_k=per_query[-1].recall_at_k,
            mrr=per_query[-1].mrr,
        )
    result = BenchmarkResult(
        pipeline_name=pipeline.name,
        config=config or {},
        k=k,
        seed_version=seed.version,
        seed_file=str(seed_file_path) if seed_file_path is not None else None,
        timestamp=datetime.now(UTC),
        per_query=per_query,
        recall=MetricSummary.from_values([q.recall_at_k for q in per_query], seed=bootstrap_seed),
        mrr=MetricSummary.from_values([q.mrr for q in per_query], seed=bootstrap_seed),
        ndcg=MetricSummary.from_values([q.ndcg_at_k for q in per_query], seed=bootstrap_seed),
    )
    log.info(
        "rag.benchmark.done",
        pipeline=pipeline.name,
        recall=result.recall.mean,
        mrr=result.mrr.mean,
        ndcg=result.ndcg.mean,
    )
    return result


# ---------- Markdown formatters ----------


def _fmt_ci(summary: MetricSummary) -> str:
    return f"{summary.mean:.3f} [{summary.ci_lo:.3f}, {summary.ci_hi:.3f}]"


def format_benchmark_markdown(result: BenchmarkResult) -> str:
    """Render one BenchmarkResult as a self-contained markdown report.

    Includes a per-query breakdown for debugging and an aggregate row with
    bootstrap CIs. Cell shape: `mean [lo, hi]`.
    """
    lines: list[str] = []
    lines.append(f"# Benchmark — `{result.pipeline_name}`")
    lines.append("")
    lines.append(f"- **k:** {result.k}")
    lines.append(f"- **n_queries:** {len(result.per_query)}")
    lines.append(f"- **seed_version:** {result.seed_version}")
    if result.seed_file:
        lines.append(f"- **seed_file:** `{result.seed_file}`")
    lines.append(f"- **timestamp:** {result.timestamp.isoformat()}")
    if result.config:
        cfg = ", ".join(f"`{k}`=`{v}`" for k, v in sorted(result.config.items()))
        lines.append(f"- **config:** {cfg}")
    lines.append("")
    lines.append("## Aggregate (mean + 95% bootstrap CI)")
    lines.append("")
    lines.append("| Metric | Value [lo, hi] |")
    lines.append("| --- | --- |")
    lines.append(f"| recall@{result.k} | {_fmt_ci(result.recall)} |")
    lines.append(f"| MRR | {_fmt_ci(result.mrr)} |")
    lines.append(f"| nDCG@{result.k} | {_fmt_ci(result.ndcg)} |")
    lines.append("")
    lines.append("## Per-query breakdown")
    lines.append("")
    lines.append(
        f"| query_id | lang | recall@{result.k} | MRR | nDCG@{result.k} "
        f"| top-{result.k} retrieved |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for q in result.per_query:
        retrieved_short = ", ".join(f"`{cid}`" for cid in q.retrieved_chunk_ids) or "—"
        lines.append(
            f"| `{q.query_id}` | {q.query_language} | "
            f"{q.recall_at_k:.3f} | {q.mrr:.3f} | {q.ndcg_at_k:.3f} | "
            f"{retrieved_short} |"
        )
    lines.append("")
    return "\n".join(lines)


def format_comparison_markdown(
    results: list[BenchmarkResult],
    paired_seed: int = 42,
    paired_resamples: int = 1000,
) -> str:
    """Render a side-by-side comparison table for multiple BenchmarkResults.

    When exactly two results are passed they are also compared with a paired
    bootstrap CI on the per-query delta — the honest small-N comparison from
    dossier §3.
    """
    if not results:
        return "# Benchmark comparison\n\n_(no results)_\n"
    k = results[0].k
    lines: list[str] = []
    lines.append("# Benchmark comparison")
    lines.append("")
    lines.append(f"- **k:** {k}")
    lines.append(f"- **n_queries:** {len(results[0].per_query)}")
    lines.append(f"- **seed_version:** {results[0].seed_version}")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    header = "| System | " + f"recall@{k} | MRR | nDCG@{k} |"
    sep = "| --- | --- | --- | --- |"
    lines.append(header)
    lines.append(sep)
    for r in results:
        lines.append(
            f"| {r.pipeline_name} | {_fmt_ci(r.recall)} | {_fmt_ci(r.mrr)} | {_fmt_ci(r.ndcg)} |"
        )
    if len(results) == 2:
        a, b = results
        ids_a = [q.query_id for q in a.per_query]
        ids_b = [q.query_id for q in b.per_query]
        if ids_a == ids_b:
            recall_delta = paired_bootstrap_ci(
                a.recall_values(),
                b.recall_values(),
                seed=paired_seed,
                n_resamples=paired_resamples,
            )
            mrr_delta = paired_bootstrap_ci(
                a.mrr_values(),
                b.mrr_values(),
                seed=paired_seed,
                n_resamples=paired_resamples,
            )
            ndcg_delta = paired_bootstrap_ci(
                a.ndcg_values(),
                b.ndcg_values(),
                seed=paired_seed,
                n_resamples=paired_resamples,
            )

            def fmt_delta(d: tuple[float, float, float]) -> str:
                mean, lo, hi = d
                sign = "+" if mean >= 0 else ""
                return f"{sign}{mean:+.3f} [{lo:+.3f}, {hi:+.3f}]"

            lines.append(
                f"| Paired Δ ({a.pipeline_name} − {b.pipeline_name}) | "
                f"{fmt_delta(recall_delta)} | {fmt_delta(mrr_delta)} | {fmt_delta(ndcg_delta)} |"
            )
            lines.append("")
            lines.append("_At N≈15 any difference whose CI crosses zero is inside the noise._")
    lines.append("")
    return "\n".join(lines)


# ---------- Convenience loaders ----------


def load_seed_file(path: str | Path = "docs/ground_truth/rag_retrieval_seed.json") -> RagSeedFile:
    """Convenience wrapper — load the project's default seed file by relative path."""
    return load_seed(path)
