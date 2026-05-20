"""BGE-small-en-v1.5 sentence-transformers wrapper for the RAG pipeline.

The dossier §2.recommendation picks ``BAAI/bge-small-en-v1.5`` (384-dim, drop-in
for the existing ``Vector(384)`` column on ``achievement_embeddings``). The
``analytics/embed.py`` MiniLM wrapper stays as a Phase 2 dependency — duplicating
the small lazy-load pattern here keeps Phase 2 clustering off the BGE upgrade
path. The model name is a module-level constant so the multilingual
mini-experiment (T10) can swap it.

The two-method interface mirrors LangChain's ``Embeddings`` ABC
(``embed_documents`` / ``embed_query``) deliberately — it is a good seam and
makes the LangChain Worktree B's drop-in adapter trivial. ``embed_query`` does
**not** prepend a bge query instruction today (see ``_QUERY_INSTRUCTION``); the
asymmetric prefix is left commented as a deliberate design seam, matching the
dossier's "one thing to get right" call.

Lazy load: importing this module must not download a model. Tests monkeypatch
``_get_model`` (mirroring ``analytics.embed``'s pattern) to stay deterministic
and offline.
"""

from typing import TYPE_CHECKING

import numpy as np
import structlog
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = structlog.get_logger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

# Query-side instruction prefix recommended by the BGE authors. Left unused
# today — a future commit may flip it on as a single source of truth once we
# benchmark whether it moves recall@5 on this corpus.
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    """Load the sentence-transformers model on first use and cache it.

    Lazy import + lazy load: importing this module must not pull in torch or
    trigger a one-off ~130 MB model download. Unit tests monkeypatch this
    function (the same pattern as ``analytics.embed._get_model``).
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("rag.embed.model.loading", model=MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
    return _model


class EmbeddingBatch(BaseModel):
    """Typed view over a batch result for callers that want shape + count."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    vectors: np.ndarray
    count: int
    dimension: int


class CustomEmbedder:
    """Two-method embedder: document-side batch + single-query.

    Stateless from the caller's perspective — the model is loaded lazily and
    shared across instances. Multiple ``CustomEmbedder()`` constructions are
    cheap and equivalent.
    """

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        # ``model_name`` is stored for introspection / future T10 routing but
        # this single-model class always loads the module-level ``MODEL_NAME``.
        # If a future caller passes a different name, today it is silently
        # ignored — pinned here so the change surfaces as a ValueError rather
        # than wrong behaviour.
        if model_name != MODEL_NAME:
            raise ValueError(
                f"CustomEmbedder is pinned to {MODEL_NAME}; got {model_name!r}. "
                "Use a separate embedder class for the multilingual fallback."
            )
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of passage texts.

        Returns one ``list[float]`` per input — a list (not a numpy array) so
        the result drops straight into pgvector via SQLAlchemy. L2-normalised
        so pgvector's cosine operator and inner-product operator agree.
        """
        if not texts:
            return []
        vectors = _get_model().encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        arr = np.asarray(vectors, dtype=np.float32)
        log.info("rag.embed.batch.done", count=len(texts), dimension=int(arr.shape[1]))
        # ``ndarray.tolist`` returns ``Any`` under numpy's stubs — narrow it
        # explicitly so the function's declared return type is honoured.
        return [[float(x) for x in row] for row in arr]

    def embed_query(self, text: str) -> list[float]:
        """Encode a single query.

        Returns a flat ``list[float]``. Mirrors ``embed_documents`` for a single
        input — no query-side instruction prefix today (see ``_QUERY_INSTRUCTION``
        for the deliberate hook).
        """
        vectors = _get_model().encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        arr = np.asarray(vectors, dtype=np.float32)
        log.info("rag.embed.query.done", dimension=int(arr.shape[1]))
        return [float(x) for x in arr[0]]
