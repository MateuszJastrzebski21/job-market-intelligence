from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import structlog
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = structlog.get_logger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load the sentence-transformers model on first use and cache it.

    Deliberately lazy: importing this module must not pull in torch or trigger
    the (~90 MB, one-time) model download — that would slow every CLI
    invocation. Unit tests monkeypatch this function so CI never downloads.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("loading embedding model", model=MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
    return _model


class EmbedRequest(BaseModel):
    """Typed input for a batch embedding call."""

    model_config = ConfigDict(extra="forbid")

    texts: list[str]


class EmbedResult(BaseModel):
    """Typed output of a batch embedding call. `vectors` stays an ndarray (not
    a list) so clustering can consume it without a copy."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    vectors: np.ndarray
    count: int
    dimension: int


def embed_batch(texts: list[str]) -> np.ndarray:
    """Encode texts into L2-normalised MiniLM embeddings.

    Returns a (len(texts), 384) float32 array. Embeddings are normalised so
    KMeans' Euclidean distance approximates cosine similarity. An empty input
    yields an empty (0, 384) array without loading the model.
    """
    if not texts:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
    vectors = _get_model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def embed(request: EmbedRequest) -> EmbedResult:
    """Typed boundary around `embed_batch` for callers that prefer models over
    bare arrays (the analytics runner)."""
    vectors = embed_batch(request.texts)
    return EmbedResult(
        vectors=vectors,
        count=int(vectors.shape[0]),
        dimension=int(vectors.shape[1]),
    )
