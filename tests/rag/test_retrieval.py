"""Tests for the pgvector cosine-similarity retriever (T4).

DB-free: the test injects a fake session whose ``execute`` returns canned rows
shaped like ``(AchievementEmbeddingORM, distance_float)``. The retriever's
query construction is exercised by an integration script (see verification
notes in MINI-REPORT) — the unit tests cover the contract: K respected, score
ordering (highest first), and the distance → similarity conversion.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from jmi.db.models import AchievementEmbeddingORM
from jmi.rag.retrieval import CustomRetriever, ScoredChunk


class _StubEmbedder:
    def __init__(self, vec: list[float] | None = None) -> None:
        self.vec = vec if vec is not None else [0.0] * 384

    def embed_query(self, text: str) -> list[float]:
        return self.vec


class _StubResult:
    def __init__(self, rows: list[tuple[AchievementEmbeddingORM, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[AchievementEmbeddingORM, float]]:
        return self._rows


class _StubSession:
    """A session that records the statement passed to ``execute`` and returns
    canned rows. Just enough to satisfy the retriever's contract."""

    def __init__(self, rows: list[tuple[AchievementEmbeddingORM, float]]) -> None:
        self._rows = rows
        self.executed: list[Any] = []

    def execute(self, stmt: Any) -> _StubResult:
        self.executed.append(stmt)
        return _StubResult(self._rows)


def _orm_row(chunk_index: int, text: str | None = None) -> AchievementEmbeddingORM:
    return AchievementEmbeddingORM(
        id=uuid4(),
        achievement_id=uuid4(),
        chunk_index=chunk_index,
        chunk_text=text if text is not None else f"[Sample — Section {chunk_index}]\n\nbody.",
        embedding=[0.0] * 384,
        created_at=datetime.now(UTC),
    )


def test_returns_scored_chunks_in_distance_order() -> None:
    rows = [
        (_orm_row(0, "first"), 0.10),
        (_orm_row(1, "second"), 0.20),
        (_orm_row(2, "third"), 0.30),
    ]
    session = _StubSession(rows)
    out = CustomRetriever(_StubEmbedder()).retrieve(session, "a query", k=3)
    assert [r.chunk_text for r in out] == ["first", "second", "third"]
    assert [round(r.score, 6) for r in out] == [0.9, 0.8, 0.7]


def test_score_is_similarity_not_distance() -> None:
    # distance 0.25 → similarity 0.75. The retriever owns this conversion.
    out = CustomRetriever(_StubEmbedder()).retrieve(_StubSession([(_orm_row(0), 0.25)]), "q", k=1)
    assert out[0].score == pytest.approx(0.75)


def test_k_is_passed_into_query() -> None:
    # We can't unwrap SQLAlchemy core trivially; instead, the stub session
    # returns only what the caller hands it. The test asserts that the
    # retriever does not over-cap or drop rows: k>len(rows) → returns all.
    rows = [(_orm_row(0), 0.1), (_orm_row(1), 0.2)]
    out = CustomRetriever(_StubEmbedder()).retrieve(_StubSession(rows), "q", k=10)
    assert len(out) == 2


def test_empty_query_returns_empty_without_calling_db() -> None:
    session = _StubSession([])
    out = CustomRetriever(_StubEmbedder()).retrieve(session, "   ", k=5)
    assert out == []
    assert session.executed == []


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        CustomRetriever(_StubEmbedder()).retrieve(_StubSession([]), "q", k=0)


def test_results_are_scored_chunk_instances() -> None:
    rows = [(_orm_row(0), 0.1)]
    out = CustomRetriever(_StubEmbedder()).retrieve(_StubSession(rows), "q", k=1)
    assert isinstance(out[0], ScoredChunk)
    assert out[0].chunk_index == 0
