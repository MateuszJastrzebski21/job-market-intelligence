"""Tests for the BGE embedder (T2).

Deterministic + offline: ``_get_model`` is monkeypatched to a fake encoder.
The real sentence-transformers load is exercised in the integration suite, not
here (mirrors H5 / E-3 — retrieval tests must not depend on a live model).
"""

from typing import Any

import numpy as np
import pytest

from jmi.rag import embedding
from jmi.rag.embedding import EMBEDDING_DIM, MODEL_NAME, CustomEmbedder


class _FakeST:
    """Deterministic stand-in for SentenceTransformer.

    Encodes by hashing each text into a fixed-shape unit vector — so the same
    text always returns the same vector and L2-normalisation is trivially true.
    """

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        self.encode_calls: list[list[str]] = []

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool = True,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        self.encode_calls.append(list(texts))
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = abs(hash(t)) % (2**31)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            if normalize_embeddings:
                v /= np.linalg.norm(v) or 1.0
            out[i] = v
        return out


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> _FakeST:
    fake = _FakeST()

    def _fake_get_model() -> Any:
        return fake

    monkeypatch.setattr(embedding, "_get_model", _fake_get_model)
    monkeypatch.setattr(embedding, "_model", None)
    return fake


def test_embed_documents_returns_one_vector_per_text(fake_model: _FakeST) -> None:
    embedder = CustomEmbedder()
    vectors = embedder.embed_documents(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


def test_dimension_is_384(fake_model: _FakeST) -> None:
    embedder = CustomEmbedder()
    assert embedder.dimension == 384
    vectors = embedder.embed_documents(["hello"])
    assert len(vectors[0]) == 384


def test_embed_query_returns_flat_vector(fake_model: _FakeST) -> None:
    embedder = CustomEmbedder()
    vec = embedder.embed_query("a query")
    assert isinstance(vec, list)
    assert len(vec) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in vec)


def test_deterministic_same_input_same_output(fake_model: _FakeST) -> None:
    embedder = CustomEmbedder()
    a = embedder.embed_documents(["x"])
    b = embedder.embed_documents(["x"])
    assert a == b


def test_batch_matches_single_for_same_text(fake_model: _FakeST) -> None:
    embedder = CustomEmbedder()
    single = embedder.embed_documents(["x"])[0]
    batched = embedder.embed_documents(["x", "y"])
    assert batched[0] == single


def test_empty_input_does_not_load_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def _should_not_be_called() -> Any:
        calls.append(True)
        raise AssertionError("model loaded for empty input")

    monkeypatch.setattr(embedding, "_get_model", _should_not_be_called)
    embedder = CustomEmbedder()
    assert embedder.embed_documents([]) == []
    assert calls == []


def test_query_vector_is_unit_norm(fake_model: _FakeST) -> None:
    embedder = CustomEmbedder()
    vec = embedder.embed_query("anything")
    norm = float(np.linalg.norm(np.asarray(vec, dtype=np.float32)))
    assert norm == pytest.approx(1.0, rel=1e-4)


def test_model_name_constant_is_bge_small() -> None:
    assert MODEL_NAME == "BAAI/bge-small-en-v1.5"


def test_constructor_rejects_other_model_names() -> None:
    with pytest.raises(ValueError, match="pinned"):
        CustomEmbedder(model_name="intfloat/multilingual-e5-small")
