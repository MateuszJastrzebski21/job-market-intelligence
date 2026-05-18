"""Embedder tests. The sentence-transformers model is faked throughout — no
torch, no model download in CI."""

from __future__ import annotations

import numpy as np

from jmi.analytics import embed


class _FakeModel:
    """Stand-in for SentenceTransformer.encode — returns fixed-shape vectors."""

    def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
        return np.ones((len(texts), embed.EMBEDDING_DIM), dtype=np.float32)


def test_model_not_loaded_on_import() -> None:
    # Importing the module must not construct the (heavy) model.
    assert embed._model is None


def test_embed_batch_shape(monkeypatch) -> None:
    monkeypatch.setattr(embed, "_get_model", _FakeModel)
    vectors = embed.embed_batch(["a", "b", "c"])
    assert vectors.shape == (3, embed.EMBEDDING_DIM)
    assert vectors.dtype == np.float32


def test_embed_batch_single(monkeypatch) -> None:
    monkeypatch.setattr(embed, "_get_model", _FakeModel)
    assert embed.embed_batch(["only one"]).shape == (1, embed.EMBEDDING_DIM)


def test_embed_batch_empty_skips_model(monkeypatch) -> None:
    calls: list[int] = []

    def _record() -> None:
        calls.append(1)

    monkeypatch.setattr(embed, "_get_model", _record)
    vectors = embed.embed_batch([])
    assert vectors.shape == (0, embed.EMBEDDING_DIM)
    assert calls == []  # empty input must not touch the model


def test_embed_typed_boundary(monkeypatch) -> None:
    monkeypatch.setattr(embed, "_get_model", _FakeModel)
    result = embed.embed(embed.EmbedRequest(texts=["x", "y"]))
    assert result.count == 2
    assert result.dimension == embed.EMBEDDING_DIM
    assert result.vectors.shape == (2, embed.EMBEDDING_DIM)
