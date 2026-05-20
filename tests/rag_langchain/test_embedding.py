"""Tests for the HuggingFaceEmbeddings adapter.

The model is heavy (~130 MB) and slow to load — we don't pull it in unit tests.
These tests assert the adapter's contract (constants, lazy load, ABC shape) and
leave model-faithful behaviour to integration tests that the audit M6 process
already gates as `slow` / live.
"""

from collections.abc import Sequence

from jmi.rag_langchain import embedding


class _FakeEmbeddings:
    """Stand-in for the real HuggingFaceEmbeddings — deterministic, no model load."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0, 1.0] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 0.0, 1.0]


def test_constants_match_dossier_recommendation() -> None:
    # Dossier §2: bge-small-en-v1.5 / 384-dim drop-in for the existing Vector(384).
    assert embedding.EMBEDDING_MODEL_NAME == "BAAI/bge-small-en-v1.5"
    assert embedding.EMBEDDING_DIM == 384


def test_get_embeddings_is_lazy(monkeypatch: object) -> None:
    """Calling get_embeddings() must hand back the cached singleton on repeat calls."""
    fake = _FakeEmbeddings()
    # Reset the singleton then plant the fake.
    embedding._embeddings = fake  # type: ignore[assignment]
    first = embedding.get_embeddings()
    second = embedding.get_embeddings()
    assert first is second is fake


def test_get_embeddings_exposes_required_methods() -> None:
    fake = _FakeEmbeddings()
    embedding._embeddings = fake  # type: ignore[assignment]
    emb = embedding.get_embeddings()
    assert hasattr(emb, "embed_documents")
    assert hasattr(emb, "embed_query")
    assert callable(emb.embed_documents)
    assert callable(emb.embed_query)


def test_fake_embeddings_round_trip_via_adapter() -> None:
    """Adapter is a pass-through to whatever Embeddings instance is cached."""
    fake = _FakeEmbeddings()
    embedding._embeddings = fake  # type: ignore[assignment]
    emb = embedding.get_embeddings()
    docs: Sequence[list[float]] = emb.embed_documents(["a", "bb"])
    assert [len(v) for v in docs] == [3, 3]
    query = emb.embed_query("hello")
    assert query[0] == 5.0
