"""Tests for the `jmi rag-embed` CLI command (T3).

DB-free: ``get_session`` is monkeypatched to a context-managed sentinel and
``ingest_embeddings`` is replaced by a recorder. The test pins the CLI's
contract (invalid UUID exits 1; summary line shape) without exercising the
real embedder or database.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from typer.testing import CliRunner

import jmi.db.base as db_base
from jmi.cli import app
from jmi.rag.ingest import IngestStats

cli = CliRunner()


@contextmanager
def _fake_session() -> Iterator[object]:
    yield object()


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(db_base, "get_session", _fake_session)
    # CustomEmbedder loads no model on construction (lazy), but we still stub
    # it to avoid any path that could touch the model on import.
    monkeypatch.setattr("jmi.rag.embedding.CustomEmbedder", lambda *a, **k: object())
    received: dict[str, Any] = {}

    def _fake_ingest(*args: Any, **kwargs: Any) -> IngestStats:
        received["args"] = args
        received["kwargs"] = kwargs
        return IngestStats(
            achievements_processed=2,
            achievements_skipped=1,
            chunks_written=8,
        )

    monkeypatch.setattr("jmi.rag.ingest.ingest_embeddings", _fake_ingest)
    return received


def test_rag_embed_prints_summary(_patched: dict[str, Any]) -> None:
    result = cli.invoke(app, ["rag-embed"])
    assert result.exit_code == 0, result.output
    assert "2 embedded, 1 skipped, 8 chunks written" in result.output


def test_rag_embed_without_ids_passes_none(_patched: dict[str, Any]) -> None:
    cli.invoke(app, ["rag-embed"])
    assert _patched["kwargs"]["achievement_ids"] is None


def test_rag_embed_with_valid_ids(_patched: dict[str, Any]) -> None:
    aid = "12345678-1234-5678-1234-567812345678"
    result = cli.invoke(app, ["rag-embed", "--achievement-id", aid])
    assert result.exit_code == 0
    passed = _patched["kwargs"]["achievement_ids"]
    assert passed is not None
    assert [str(u) for u in passed] == [aid]


def test_rag_embed_with_invalid_uuid_exits_one() -> None:
    result = cli.invoke(app, ["rag-embed", "--achievement-id", "not-a-uuid"])
    assert result.exit_code == 1
    assert "invalid --achievement-id" in result.output
