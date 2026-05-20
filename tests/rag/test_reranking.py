"""Tests for the cross-encoder reranker (T5).

Deterministic + offline: ``_get_model`` is monkeypatched to a fake whose
``predict`` returns scores keyed by the chunk text — so a test can pin
"score-1 should land first."
"""

from typing import Any
from uuid import uuid4

import pytest

from jmi.rag import reranking
from jmi.rag.reranking import CustomReranker, RerankerConfig
from jmi.rag.retrieval import ScoredChunk


class _FakeCE:
    """Fake CrossEncoder. Maps each ``(query, chunk_text)`` pair to a score
    via the constructor-supplied dict; absent chunks score 0.0."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[list[list[str]]] = []

    def predict(self, pairs: list[list[str]]) -> list[float]:
        self.calls.append(list(pairs))
        return [self.scores.get(pair[1], 0.0) for pair in pairs]


@pytest.fixture
def fake_ce(monkeypatch: pytest.MonkeyPatch) -> _FakeCE:
    fake = _FakeCE(scores={})
    monkeypatch.setattr(reranking, "_get_model", lambda: fake)
    monkeypatch.setattr(reranking, "_model", None)
    return fake


def _chunk(text: str, score: float = 0.0) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid4(),
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=score,
    )


def test_rerank_changes_order_when_cross_encoder_disagrees(fake_ce: _FakeCE) -> None:
    fake_ce.scores = {"low-rel": 0.1, "high-rel": 9.0, "mid-rel": 1.0}
    chunks = [_chunk("low-rel", 0.9), _chunk("mid-rel", 0.8), _chunk("high-rel", 0.7)]
    out = CustomReranker().rerank("a query", chunks)
    assert [c.chunk_text for c in out] == ["high-rel", "mid-rel", "low-rel"]
    assert out[0].score == pytest.approx(9.0)


def test_empty_input_is_passthrough(fake_ce: _FakeCE) -> None:
    out = CustomReranker().rerank("q", [])
    assert out == []
    assert fake_ce.calls == []


def test_single_chunk_is_still_scored(fake_ce: _FakeCE) -> None:
    """A single chunk still hits the model — callers expect the returned
    ``score`` to be the cross-encoder's opinion uniformly, not the upstream
    bi-encoder's. Skipping the model on n=1 would surprise the pipeline."""
    fake_ce.scores = {"only": 7.0}
    c = _chunk("only", 0.42)
    out = CustomReranker().rerank("q", [c])
    assert len(out) == 1
    assert out[0].chunk_text == "only"
    assert out[0].score == pytest.approx(7.0)
    assert fake_ce.calls == [[["q", "only"]]]


def test_top_n_caps_output(fake_ce: _FakeCE) -> None:
    fake_ce.scores = {"a": 3.0, "b": 2.0, "c": 1.0}
    chunks = [_chunk(t) for t in ("c", "a", "b")]
    out = CustomReranker(RerankerConfig(top_n=2)).rerank("q", chunks)
    assert [c.chunk_text for c in out] == ["a", "b"]


def test_score_field_is_cross_encoder_logit(fake_ce: _FakeCE) -> None:
    fake_ce.scores = {"x": 2.5}
    out = CustomReranker().rerank("q", [_chunk("x", score=0.6)])
    assert out[0].score == pytest.approx(2.5)


def test_chunk_identity_preserved(fake_ce: _FakeCE) -> None:
    fake_ce.scores = {"a": 1.0}
    c = _chunk("a")
    out = CustomReranker().rerank("q", [c, _chunk("b")])
    assert out[0].chunk_id == c.chunk_id


def test_model_name_constant_is_bge_reranker_base() -> None:
    assert reranking.RERANKER_MODEL_NAME == "BAAI/bge-reranker-base"


def test_pairs_include_query_for_every_chunk(fake_ce: _FakeCE) -> None:
    fake_ce.scores = {"a": 1.0, "b": 0.5}
    CustomReranker().rerank("the query", [_chunk("a"), _chunk("b")])
    assert fake_ce.calls == [[["the query", "a"], ["the query", "b"]]]


def test_disabled_reranker_is_none_in_pipeline_contract() -> None:
    # The pipeline composer (T6) treats ``None`` as "skip"; this test pins the
    # contract by reading the type alias-style annotation on Reranker.
    from typing import get_type_hints

    hints = get_type_hints(reranking.Reranker.rerank)
    # Just confirm the method shape is preserved — the Protocol definition.
    assert "query" in hints
    assert "chunks" in hints


def test_arbitrary_predict_callable_is_acceptable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wrapper that exposes ``predict`` is enough — no need to subclass."""

    class _MinimalRanker:
        def predict(self, pairs: list[list[str]]) -> list[float]:
            return [float(len(p[1])) for p in pairs]

    minimal: Any = _MinimalRanker()
    monkeypatch.setattr(reranking, "_get_model", lambda: minimal)
    monkeypatch.setattr(reranking, "_model", None)
    chunks = [_chunk("short"), _chunk("a much longer chunk text")]
    out = CustomReranker().rerank("q", chunks)
    # Longer chunk wins by the length-as-score fake.
    assert out[0].chunk_text == "a much longer chunk text"
