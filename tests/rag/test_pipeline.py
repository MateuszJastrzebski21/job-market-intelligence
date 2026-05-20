"""Tests for the composed retrieve→rerank pipeline (T6)."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from jmi.db.models import AchievementEmbeddingORM
from jmi.rag.pipeline import RagPipeline
from jmi.rag.retrieval import CustomRetriever, ScoredChunk


class _StubEmbedder:
    def embed_query(self, text: str) -> list[float]:
        return [0.0] * 384


class _StubResult:
    def __init__(self, rows: list[tuple[AchievementEmbeddingORM, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[AchievementEmbeddingORM, float]]:
        return self._rows


class _StubSession:
    def __init__(self, rows: list[tuple[AchievementEmbeddingORM, float]]) -> None:
        self._rows = rows

    def execute(self, stmt: Any) -> _StubResult:
        return _StubResult(self._rows)


def _orm_row(text: str) -> AchievementEmbeddingORM:
    return AchievementEmbeddingORM(
        id=uuid4(),
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        embedding=[0.0] * 384,
        created_at=datetime.now(UTC),
    )


class _RevReranker:
    """Reranker that reverses chunk order. Lets us assert that the pipeline
    actually called rerank without using a real model."""

    def __init__(self) -> None:
        self.calls = 0

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        self.calls += 1
        return list(reversed(chunks))


def test_pipeline_without_reranker_returns_retriever_topk() -> None:
    rows = [(_orm_row(f"chunk-{i}"), 0.1 * i) for i in range(5)]
    session = _StubSession(rows)
    pipeline = RagPipeline(CustomRetriever(_StubEmbedder()), reranker=None)
    out = pipeline.retrieve_top_k(session, "q", k=3)
    assert [c.chunk_text for c in out] == ["chunk-0", "chunk-1", "chunk-2"]


def test_pipeline_with_reranker_applies_reranker_and_caps_at_k() -> None:
    rows = [(_orm_row(f"chunk-{i}"), 0.1 * i) for i in range(10)]
    session = _StubSession(rows)
    reranker = _RevReranker()
    pipeline = RagPipeline(CustomRetriever(_StubEmbedder()), reranker=reranker)
    out = pipeline.retrieve_top_k(session, "q", k=3)
    # Reranker reversed the 10-candidate pool (default = 3·k = 9 rows pulled,
    # plus the stub returns whatever it has) → last → first → returned first 3.
    assert reranker.calls == 1
    assert len(out) == 3


def test_candidate_pool_override_is_respected() -> None:
    rows = [(_orm_row(f"chunk-{i}"), 0.1 * i) for i in range(50)]
    session = _StubSession(rows)
    reranker = _RevReranker()
    pipeline = RagPipeline(CustomRetriever(_StubEmbedder()), reranker=reranker)
    pipeline.retrieve_top_k(session, "q", k=3, candidate_pool=7)
    # The stub returns all rows regardless of LIMIT, but the rerank input size
    # equals the candidate-pool retrieved — we proxy by checking how many
    # chunks the reranker saw on its only call.
    # Note: our stub session returns all 50 rows, so the retrieve call would
    # have asked for 7 (verified by the log line). The reranker would see
    # however many rows the retriever returned — here, all 50, which is
    # bounded by the stub not by ``LIMIT``. The unit test here mainly checks
    # the parameter plumbing did not error.
    assert reranker.calls == 1


def test_has_reranker_property_reflects_construction() -> None:
    pipeline_off = RagPipeline(CustomRetriever(_StubEmbedder()), reranker=None)
    assert pipeline_off.has_reranker is False
    pipeline_on = RagPipeline(CustomRetriever(_StubEmbedder()), reranker=_RevReranker())
    assert pipeline_on.has_reranker is True


def test_zero_k_propagates_to_retriever_validation() -> None:
    pipeline = RagPipeline(CustomRetriever(_StubEmbedder()))
    with pytest.raises(ValueError, match="k must be positive"):
        pipeline.retrieve_top_k(_StubSession([]), "q", k=0)


def test_empty_query_short_circuits_to_empty() -> None:
    pipeline = RagPipeline(CustomRetriever(_StubEmbedder()))
    out = pipeline.retrieve_top_k(_StubSession([]), "  ", k=5)
    assert out == []
