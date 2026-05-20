"""Tests for the LangChain ingest pipeline.

DB-free: the PGVectorStore interaction is monkeypatched with a fake that records
calls. The deterministic id derivation and chunk-emission flow are pure functions
and tested directly.
"""

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from jmi.models.achievement import Achievement
from jmi.rag_langchain import ingest
from jmi.rag_langchain.chunking import chunk_achievement
from jmi.rag_langchain.ingest import (
    COLLECTION_TABLE,
    chunks_to_ids,
    ingest_chunks,
)


def _make_achievement(title: str = "A") -> Achievement:
    return Achievement(
        id=uuid4(),
        title=title,
        source_path=Path("x/a.md"),
        context="ctx body",
        approach="apr body",
        impact="imp body",
        lessons="les body",
    )


class _FakeStore:
    """Stand-in for PGVectorStore that records add_documents calls."""

    def __init__(self) -> None:
        self.added_documents: list[Any] = []
        self.added_ids: list[list[str]] = []

    def add_documents(self, documents: list[Any], ids: list[str]) -> None:
        self.added_documents.extend(documents)
        self.added_ids.append(list(ids))


def test_collection_table_constant() -> None:
    # ADR-0015b §4: dedicated table separates LangChain's schema from custom side.
    assert COLLECTION_TABLE == "langchain_achievement_embeddings"


def test_chunks_to_ids_is_deterministic() -> None:
    a = _make_achievement()
    docs = chunk_achievement(a)
    ids_1 = chunks_to_ids(docs)
    ids_2 = chunks_to_ids(docs)
    assert ids_1 == ids_2
    assert len(ids_1) == len(docs)
    # All ids are unique within an achievement.
    assert len(set(ids_1)) == len(ids_1)


def test_chunks_to_ids_differs_by_achievement() -> None:
    a1 = _make_achievement("One")
    a2 = _make_achievement("Two")
    ids_1 = chunks_to_ids(chunk_achievement(a1))
    ids_2 = chunks_to_ids(chunk_achievement(a2))
    assert set(ids_1).isdisjoint(set(ids_2))


def test_ingest_chunks_writes_one_id_batch_for_corpus() -> None:
    a1 = _make_achievement("A1")
    a2 = _make_achievement("A2")
    store = _FakeStore()
    written = ingest_chunks(store, [a1, a2])  # type: ignore[arg-type]
    assert written == 8  # 4 sections × 2 achievements
    assert len(store.added_documents) == 8
    # Single add_documents call → single id batch
    assert len(store.added_ids) == 1
    assert len(store.added_ids[0]) == 8


def test_ingest_chunks_empty_input_skips_store() -> None:
    store = _FakeStore()
    written = ingest_chunks(store, [])  # type: ignore[arg-type]
    assert written == 0
    assert store.added_documents == []
    assert store.added_ids == []


def test_ingest_chunks_idempotency_uses_same_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-ingesting the same achievement must reuse its deterministic ids."""
    a = _make_achievement()
    store = _FakeStore()
    ingest_chunks(store, [a])  # type: ignore[arg-type]
    first_ids = store.added_ids[0][:]
    ingest_chunks(store, [a])  # type: ignore[arg-type]
    second_ids = store.added_ids[1][:]
    assert first_ids == second_ids


def test_get_pg_engine_uses_settings_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine factory passes the settings DSN through to PGEngine.from_connection_string."""
    captured: dict[str, Any] = {}

    class _DummyEngine:
        pass

    def _fake_from_conn_string(url: str, **kwargs: Any) -> _DummyEngine:
        captured["url"] = url
        return _DummyEngine()

    monkeypatch.setattr(
        "langchain_postgres.PGEngine.from_connection_string",
        _fake_from_conn_string,
    )
    ingest.get_pg_engine("postgresql+psycopg://u:p@h/db")
    assert captured["url"] == "postgresql+psycopg://u:p@h/db"
