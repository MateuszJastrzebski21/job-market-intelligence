"""Unit tests for the retrieval benchmark harness.

No DB, no embedder, no LangChain — exercises the harness via `StubPipeline`
so the tests run on the C branch alone (worktree A's and B's pipeline modules
are imported only via duck-typing at runtime).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from jmi.evaluation.benchmark import (
    MetricSummary,
    QueryResult,
    ScoredChunkAdapter,
    StubPipeline,
    benchmark_pipeline,
    format_benchmark_markdown,
    format_comparison_markdown,
)
from jmi.evaluation.retrieval_seed import RagSeedEntry, RagSeedFile


def _seed(entries: list[RagSeedEntry], version: str = "1") -> RagSeedFile:
    return RagSeedFile(version=version, entries=entries)


def _entry(
    query_id: str,
    query: str,
    relevant: list[str],
    language: str = "en",
) -> RagSeedEntry:
    return RagSeedEntry(
        id=query_id,
        query=query,
        query_language=language,  # type: ignore[arg-type]
        relevant_chunk_ids=relevant,
    )


# ---------- benchmark_pipeline ----------


def test_benchmark_pipeline_perfect_retriever() -> None:
    seed = _seed(
        [
            _entry("q1", "java backend", ["foo::context", "foo::approach"]),
            _entry("q2", "python ml", ["bar::approach"]),
        ]
    )
    pipeline = StubPipeline(
        name="perfect",
        answers={
            "java backend": ["foo::context", "foo::approach", "baz::lessons"],
            "python ml": ["bar::approach", "baz::lessons"],
        },
    )
    result = benchmark_pipeline(pipeline, seed, k=5)
    assert result.pipeline_name == "perfect"
    assert result.k == 5
    assert len(result.per_query) == 2
    assert result.recall.mean == 1.0  # both queries: all relevant in top 5
    assert result.mrr.mean == 1.0


def test_benchmark_pipeline_misses() -> None:
    seed = _seed([_entry("q1", "q", ["foo::context"])])
    pipeline = StubPipeline(name="empty", answers={})
    result = benchmark_pipeline(pipeline, seed, k=5)
    assert result.per_query[0].recall_at_k == 0.0
    assert result.per_query[0].mrr == 0.0
    assert result.recall.mean == 0.0


def test_benchmark_pipeline_records_metadata() -> None:
    seed = _seed([_entry("q1", "q", ["foo::context"])])
    pipeline = StubPipeline(name="p", answers={"q": ["foo::context"]})
    result = benchmark_pipeline(
        pipeline,
        seed,
        k=3,
        config={"reranker": "bge", "embedder": "bge-small"},
        seed_file_path="docs/ground_truth/rag_retrieval_seed.json",
    )
    assert result.k == 3
    assert result.config == {"reranker": "bge", "embedder": "bge-small"}
    assert result.seed_file == "docs/ground_truth/rag_retrieval_seed.json"
    assert result.seed_version == "1"
    assert result.timestamp is not None


def test_benchmark_pipeline_per_query_preserves_order() -> None:
    seed = _seed(
        [
            _entry("q1", "a", ["foo::context"]),
            _entry("q2", "b", ["bar::approach"]),
            _entry("q3", "c", ["baz::impact"]),
        ]
    )
    pipeline = StubPipeline(
        name="p",
        answers={"a": ["foo::context"], "b": ["bar::approach"], "c": ["baz::impact"]},
    )
    result = benchmark_pipeline(pipeline, seed, k=5)
    assert [q.query_id for q in result.per_query] == ["q1", "q2", "q3"]


def test_benchmark_pipeline_partial_recall() -> None:
    seed = _seed([_entry("q1", "q", ["foo::context", "foo::approach", "foo::impact"])])
    pipeline = StubPipeline(name="p", answers={"q": ["foo::context", "x::y"]})
    result = benchmark_pipeline(pipeline, seed, k=5)
    # 1 of 3 relevant in top-5
    assert result.per_query[0].recall_at_k == pytest.approx(1 / 3)
    # mrr: first hit at rank 1
    assert result.per_query[0].mrr == 1.0


def test_benchmark_pipeline_rejects_zero_k() -> None:
    seed = _seed([_entry("q1", "q", ["foo::context"])])
    pipeline = StubPipeline(name="p", answers={})
    with pytest.raises(ValueError):
        benchmark_pipeline(pipeline, seed, k=0)


# ---------- ScoredChunkAdapter ----------


class _FakeScoredChunk:
    """Minimal duck-typed stand-in for either RagPipeline's ScoredChunk."""

    def __init__(self, achievement_id: object, chunk_index: int) -> None:
        self.achievement_id = achievement_id
        self.chunk_index = chunk_index


def test_scored_chunk_adapter_resolves_canonical_ids() -> None:
    aid1, aid2 = uuid4(), uuid4()
    source_paths = {aid1: "achievements/foo.md", aid2: "achievements/bar.md"}

    def resolver(achievement_id, chunk_index):  # type: ignore[no-untyped-def]
        stem = source_paths[achievement_id].rsplit("/", 1)[-1].removesuffix(".md")
        section = ("context", "approach", "impact", "lessons")[chunk_index]
        return f"{stem}::{section}"

    def fake_retrieve(query: str, k: int):  # type: ignore[no-untyped-def]
        return [_FakeScoredChunk(aid1, 0), _FakeScoredChunk(aid2, 2)][:k]

    adapter = ScoredChunkAdapter("test", fake_retrieve, resolver)
    ids = adapter.retrieve_chunk_ids("any query", k=5)
    assert ids == ["foo::context", "bar::impact"]


def test_scored_chunk_adapter_respects_k() -> None:
    aid1 = uuid4()

    def resolver(achievement_id, chunk_index):  # type: ignore[no-untyped-def]
        return f"foo::{('context', 'approach', 'impact', 'lessons')[chunk_index]}"

    def fake_retrieve(query: str, k: int):  # type: ignore[no-untyped-def]
        # caller is responsible for honouring k — adapter does not re-slice
        return [_FakeScoredChunk(aid1, i) for i in range(k)]

    adapter = ScoredChunkAdapter("test", fake_retrieve, resolver)
    assert len(adapter.retrieve_chunk_ids("q", k=3)) == 3


# ---------- MetricSummary ----------


def test_metric_summary_constant_values() -> None:
    summary = MetricSummary.from_values([0.5, 0.5, 0.5, 0.5], seed=0)
    assert summary.mean == 0.5
    assert summary.ci_lo == 0.5
    assert summary.ci_hi == 0.5


def test_metric_summary_empty_values() -> None:
    summary = MetricSummary.from_values([])
    assert summary.mean == 0.0


# ---------- format_benchmark_markdown ----------


def test_format_benchmark_markdown_contains_aggregate_and_per_query() -> None:
    seed = _seed([_entry("q1", "java", ["foo::context"])])
    pipeline = StubPipeline(name="custom", answers={"java": ["foo::context"]})
    result = benchmark_pipeline(pipeline, seed, k=5)
    md = format_benchmark_markdown(result)
    assert "# Benchmark — `custom`" in md
    assert "recall@5" in md
    assert "MRR" in md
    assert "## Per-query breakdown" in md
    assert "`q1`" in md
    assert "`foo::context`" in md


def test_format_benchmark_markdown_includes_config_when_present() -> None:
    seed = _seed([_entry("q1", "q", ["foo::context"])])
    pipeline = StubPipeline(name="p", answers={})
    result = benchmark_pipeline(pipeline, seed, k=5, config={"rerank": True})
    md = format_benchmark_markdown(result)
    assert "`rerank`=`True`" in md


# ---------- format_comparison_markdown ----------


def test_format_comparison_markdown_two_systems_paired_delta() -> None:
    seed = _seed(
        [
            _entry("q1", "java", ["foo::context"]),
            _entry("q2", "python", ["bar::approach"]),
        ]
    )
    p_good = StubPipeline(
        name="good", answers={"java": ["foo::context"], "python": ["bar::approach"]}
    )
    p_bad = StubPipeline(name="bad", answers={"java": ["x::y"], "python": ["x::y"]})
    r_good = benchmark_pipeline(p_good, seed, k=5)
    r_bad = benchmark_pipeline(p_bad, seed, k=5)
    md = format_comparison_markdown([r_good, r_bad])
    assert "good" in md
    assert "bad" in md
    assert "Paired Δ" in md
    assert "inside the noise" in md


def test_format_comparison_markdown_single_system_no_delta() -> None:
    seed = _seed([_entry("q1", "q", ["foo::context"])])
    pipeline = StubPipeline(name="solo", answers={"q": ["foo::context"]})
    result = benchmark_pipeline(pipeline, seed, k=5)
    md = format_comparison_markdown([result])
    assert "solo" in md
    assert "Paired Δ" not in md


def test_format_comparison_markdown_no_results() -> None:
    md = format_comparison_markdown([])
    assert "no results" in md


# ---------- QueryResult / BenchmarkResult basic shape ----------


def test_query_result_is_frozen() -> None:
    q = QueryResult(
        query_id="q1",
        query="q",
        query_language="en",
        relevant_chunk_ids=["foo::context"],
        retrieved_chunk_ids=["foo::context"],
        recall_at_k=1.0,
        mrr=1.0,
        ndcg_at_k=1.0,
    )
    with pytest.raises((TypeError, ValueError)):
        q.query_id = "q2"  # type: ignore[misc]


def test_benchmark_result_exposes_value_vectors() -> None:
    seed = _seed(
        [
            _entry("q1", "a", ["foo::context"]),
            _entry("q2", "b", ["bar::approach"]),
        ]
    )
    pipeline = StubPipeline(name="p", answers={"a": ["foo::context"], "b": ["x::y"]})
    result = benchmark_pipeline(pipeline, seed, k=5)
    assert result.recall_values() == [1.0, 0.0]
    assert result.mrr_values() == [1.0, 0.0]
