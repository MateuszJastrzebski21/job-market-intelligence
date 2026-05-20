"""Cross-encoder reranker — ``BAAI/bge-reranker-base`` (T5).

A drop-in stage between the bi-encoder retriever (T4) and the generator (T7).
At 24-80 chunks the candidate set is nearly the whole corpus, so reranking
is unlikely to move recall@5 outside the §3 noise band — but the seam matters
for the LangChain comparison (B's ``ContextualCompressionRetriever`` is the
natural foil) and for the blog post line "left out of the first cut, here is
where it plugs in" (dossier §4).

The default ``CustomReranker`` lazy-loads the cross-encoder. A ``None``
reranker is the documented "skip" — the pipeline composer (T6) calls
``rerank`` only when one is configured, and pass-through behaviour is
preserved on disable.
"""

from typing import TYPE_CHECKING, Any, Protocol, cast

import structlog
from pydantic import BaseModel, ConfigDict, Field

from jmi.rag.retrieval import ScoredChunk

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

log = structlog.get_logger(__name__)

RERANKER_MODEL_NAME = "BAAI/bge-reranker-base"

_model: "CrossEncoder | None" = None


def _get_model() -> "CrossEncoder":
    """Load the cross-encoder lazily and cache it (same shape as embedder)."""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        log.info("rag.rerank.model.loading", model=RERANKER_MODEL_NAME)
        _model = CrossEncoder(RERANKER_MODEL_NAME)
    return _model


class Reranker(Protocol):
    """The drop-in interface.

    A pipeline (T6) accepts ``Reranker | None``; ``None`` means "do not
    rerank — pass embedding order through."
    """

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]: ...


class RerankerConfig(BaseModel):
    """Optional knobs the pipeline can pin per-run (kept Pydantic so callers
    serialise/log consistently). Currently only a top-N cap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    top_n: int | None = Field(default=None, ge=1)


class CustomReranker:
    """Cross-encoder reranker over ``(query, chunk_text)`` pairs.

    The new ``score`` field replaces the bi-encoder cosine similarity with the
    cross-encoder logit. Scores are *not* on the same scale as the bi-encoder's
    cosine — the new ordering matters, not the absolute number — but the field
    is reused so the pipeline interface stays uniform.
    """

    def __init__(self, config: RerankerConfig | None = None) -> None:
        self._config = config or RerankerConfig()

    @property
    def model_name(self) -> str:
        return RERANKER_MODEL_NAME

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        """Re-sort ``chunks`` by cross-encoder score, descending.

        Empty input is a fast path that does not touch the model. Otherwise
        every ``(query, chunk_text)`` pair (including the trivial 1-element
        case) is scored in one batched call — a single forward pass is cheap
        and callers expect the returned ``score`` to be the cross-encoder's
        opinion, not the upstream bi-encoder's.
        """
        if not chunks:
            return []
        pairs: list[list[str]] = [[query, c.chunk_text] for c in chunks]
        # ``CrossEncoder.predict`` accepts ``list[PairInput]`` where
        # ``PairInput`` is sentence-transformers' wide multimodal union — but
        # the type alias lives at ``sentence_transformers.cross_encoder.model``
        # (a private submodule). Coupling JMI's type to that path would be
        # fragile; ``cast`` here documents the lossy-stub crossing without a
        # blanket type:ignore.
        raw_scores = _get_model().predict(cast(Any, pairs))
        scores: list[float] = [float(x) for x in raw_scores]
        reordered = sorted(
            (c.model_copy(update={"score": s}) for c, s in zip(chunks, scores, strict=True)),
            key=lambda c: c.score,
            reverse=True,
        )
        cap = self._config.top_n
        result = reordered if cap is None else reordered[:cap]
        log.info(
            "rag.rerank.done",
            input_count=len(chunks),
            output_count=len(result),
            top_chunk_id=str(result[0].chunk_id) if result else None,
        )
        return result
