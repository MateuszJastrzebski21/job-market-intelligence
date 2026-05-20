"""Tests for the `jmi rag-query` CLI command (T6)."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest
from typer.testing import CliRunner

import jmi.db.base as db_base
from jmi.cli import app
from jmi.rag.retrieval import ScoredChunk

cli = CliRunner()


@contextmanager
def _fake_session() -> Iterator[object]:
    yield object()


def _scored(text: str, score: float) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid4(),
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=score,
    )


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(db_base, "get_session", _fake_session)
    # Stub out the model-loading constructors — the CLI test must not pull
    # weights at import time.
    monkeypatch.setattr("jmi.rag.embedding.CustomEmbedder", lambda *a, **k: object())
    monkeypatch.setattr("jmi.rag.reranking.CustomReranker", lambda *a, **k: object())
    received: dict[str, Any] = {}

    class _StubPipeline:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            received["args"] = args
            received["kwargs"] = kwargs

        @property
        def has_reranker(self) -> bool:
            return received["args"][1] is not None

        def retrieve_top_k(
            self, session: object, query: str, k: int = 5, **kwargs: Any
        ) -> list[ScoredChunk]:
            received["query"] = query
            received["k"] = k
            return [
                _scored("[Title A — Section]\nbody-a", 0.85),
                _scored("[Title B — Section]\nbody-b", 0.72),
            ]

    monkeypatch.setattr("jmi.rag.pipeline.RagPipeline", _StubPipeline)
    return received


def test_rag_query_prints_top_k(_patched: dict[str, Any]) -> None:
    result = cli.invoke(app, ["rag-query", "java backend"])
    assert result.exit_code == 0, result.output
    assert "top-5 via rerank" in result.output
    assert "[Title A — Section]" in result.output
    assert "[Title B — Section]" in result.output


def test_rag_query_no_rerank_flag(_patched: dict[str, Any]) -> None:
    result = cli.invoke(app, ["rag-query", "java", "--no-rerank"])
    assert result.exit_code == 0, result.output
    assert "via bi-encoder" in result.output
    assert _patched["args"][1] is None


def test_rag_query_k_option(_patched: dict[str, Any]) -> None:
    result = cli.invoke(app, ["rag-query", "java", "--k", "3"])
    assert result.exit_code == 0, result.output
    assert _patched["k"] == 3


def test_rag_query_rejects_zero_k() -> None:
    result = cli.invoke(app, ["rag-query", "q", "--k", "0"])
    assert result.exit_code == 1
    assert "must be positive" in result.output
