"""Tests for the LangChain retriever wrapper.

DB-free: the PGVectorStore interaction is monkeypatched with a fake that returns
canned (document, distance) pairs. Asserts the contract: score direction
inverted (lower distance → higher score), metadata round-trips, K respected.
"""

from typing import Any

from langchain_core.documents import Document

from jmi.rag_langchain.retrieval import (
    ScoredChunk,
    _distance_to_score,
    retrieve,
)


class _FakeStore:
    def __init__(self, returns: list[tuple[Document, float]]) -> None:
        self._returns = returns
        self.last_k: int | None = None

    def similarity_search_with_score(self, query: str, k: int = 5) -> list[tuple[Document, float]]:
        self.last_k = k
        return self._returns[:k]


def _doc(
    chunk_id: str = "11111111-1111-1111-1111-111111111111",
    achievement_id: str = "22222222-2222-2222-2222-222222222222",
    chunk_index: int = 0,
    section: str = "impact",
    text: str = "body",
) -> Document:
    return Document(
        page_content=text,
        metadata={
            "langchain_id": chunk_id,
            "achievement_id": achievement_id,
            "chunk_index": chunk_index,
            "section": section,
            "title": "T",
        },
    )


def test_distance_to_score_inverts() -> None:
    assert _distance_to_score(0.0) == 1.0
    assert _distance_to_score(1.0) == 0.0


def test_retrieve_respects_k() -> None:
    store = _FakeStore([(_doc(), 0.1), (_doc(), 0.2), (_doc(), 0.3)])
    result = retrieve(store, "q", k=2)  # type: ignore[arg-type]
    assert len(result) == 2
    assert store.last_k == 2


def test_retrieve_preserves_distance_order_after_score_inversion() -> None:
    # distance order: 0.1 < 0.2 < 0.3 ↔ score order: 0.9 > 0.8 > 0.7
    store = _FakeStore(
        [
            (_doc(text="closest"), 0.1),
            (_doc(text="middle"), 0.2),
            (_doc(text="farthest"), 0.3),
        ]
    )
    result = retrieve(store, "q", k=3)  # type: ignore[arg-type]
    assert [r.chunk_text for r in result] == ["closest", "middle", "farthest"]
    assert result[0].score > result[1].score > result[2].score


def test_retrieve_round_trips_metadata() -> None:
    store = _FakeStore(
        [
            (
                _doc(
                    chunk_id="cid1",
                    achievement_id="aid1",
                    chunk_index=2,
                    section="lessons",
                    text="content",
                ),
                0.25,
            )
        ]
    )
    result = retrieve(store, "q", k=1)  # type: ignore[arg-type]
    assert result == [
        ScoredChunk(
            chunk_id="cid1",
            achievement_id="aid1",
            chunk_index=2,
            section="lessons",
            chunk_text="content",
            score=0.75,
        )
    ]


def test_retrieve_handles_missing_metadata_gracefully() -> None:
    # PGVectorStore default metadata column is langchain_metadata (JSONB) — but
    # if a row got written without our metadata keys, the retriever defaults
    # rather than crashes.
    sparse_doc = Document(page_content="lonely", metadata={})
    store = _FakeStore([(sparse_doc, 0.4)])
    result = retrieve(store, "q", k=1)  # type: ignore[arg-type]
    assert result[0].chunk_id == ""
    assert result[0].chunk_index == -1
    assert result[0].section == "unknown"
    assert result[0].chunk_text == "lonely"


def test_retrieve_empty_store_returns_empty(monkeypatch: Any) -> None:
    store = _FakeStore([])
    result = retrieve(store, "q", k=5)  # type: ignore[arg-type]
    assert result == []
