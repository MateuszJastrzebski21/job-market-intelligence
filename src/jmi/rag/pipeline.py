"""End-to-end retrieval pipeline (T6) — retrieve → optional rerank.

Composes the embedder, retriever, and an optional reranker so the CLI and the
benchmark harness (Worktree C) share one entry point. Generation is *not*
composed here — T7 lives in a separate module so a future caller can do
retrieve-only without paying for the LLM step.

Design:

- ``retrieve_top_k`` is the only public method.
- ``rerank`` is opt-in via the ``reranker`` constructor argument; passing
  ``None`` skips reranking and the function falls through with the embedding
  order untouched.
- A ``Session`` is injected per call (same shape as ``CustomRetriever``).
"""

import structlog
from sqlalchemy.orm import Session

from jmi.rag.reranking import Reranker
from jmi.rag.retrieval import CustomRetriever, ScoredChunk

log = structlog.get_logger(__name__)


class RagPipeline:
    """Compose retrieval and optional reranking into one ``retrieve_top_k`` call.

    Construction is cheap — no model load happens until ``retrieve_top_k`` runs
    against a session.
    """

    def __init__(self, retriever: CustomRetriever, reranker: Reranker | None = None) -> None:
        self._retriever = retriever
        self._reranker = reranker

    @property
    def has_reranker(self) -> bool:
        return self._reranker is not None

    def retrieve_top_k(
        self,
        session: Session,
        query: str,
        k: int = 5,
        *,
        candidate_pool: int | None = None,
    ) -> list[ScoredChunk]:
        """Return the top-K chunks for ``query``.

        Without a reranker the retriever's top-K is returned directly. With a
        reranker, the retriever returns a *candidate pool* (default 3·K so the
        cross-encoder has room to reorder), the reranker scores it, and the
        top-K of the reranked list is returned. The pool size is exposed for
        the benchmark harness to vary as a separate axis.
        """
        if not self._reranker:
            return self._retriever.retrieve(session, query, k=k)
        pool = candidate_pool if candidate_pool is not None else max(k * 3, k)
        candidates = self._retriever.retrieve(session, query, k=pool)
        log.info(
            "rag.pipeline.candidates",
            candidate_pool=len(candidates),
            requested_pool=pool,
            k=k,
        )
        reranked = self._reranker.rerank(query, candidates)
        return reranked[:k]
