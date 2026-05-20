"""LangChain RAG pipeline — public surface mirroring Worktree A's RagPipeline.

`RagPipeline` exposes the two methods Worktree C's benchmark harness calls:

    pipeline = RagPipeline(...)
    pipeline.retrieve_top_k(query, k=5, rerank=True) -> list[ScoredChunk]
    pipeline.generate_bullets(job_description, k=5, rerank=True) -> str

The pipeline composes the LangChain primitives (PGVectorStore retriever →
optional reranker → LCEL chain) into one object so the benchmark can swap it
in for `jmi.rag.pipeline.RagPipeline` without touching the harness.

Security (S-2): no chunk text in logs.
"""

from typing import TYPE_CHECKING

import structlog
from langchain_core.runnables import Runnable

from jmi.rag_langchain.embedding import get_embeddings
from jmi.rag_langchain.generation import (
    DEFAULT_MODEL,
    build_chain,
    format_achievements,
)
from jmi.rag_langchain.ingest import (
    ensure_collection_table,
    get_pg_engine,
    get_vector_store,
)
from jmi.rag_langchain.reranking import compose_with_reranker, compose_without_reranker
from jmi.rag_langchain.retrieval import ScoredChunk, _derive_chunk_id, retrieve

if TYPE_CHECKING:
    from langchain_postgres import PGVectorStore

log = structlog.get_logger(__name__)


class RagPipeline:
    """Composed retrieval + reranking + generation, LangChain-backed.

    The pipeline owns the PGVectorStore and the lazy generation chain. The
    embeddings and PGEngine come from the module-level factories so production
    callers usually don't construct any of the dependencies themselves.

    The reranker is built lazily on first reranked retrieval — its model load
    is a ~280 MB download that we don't want to incur in tests that never
    rerank.
    """

    def __init__(
        self,
        store: "PGVectorStore | None" = None,
        generation_chain: Runnable[dict[str, object], str] | None = None,
        generation_model: str = DEFAULT_MODEL,
    ) -> None:
        if store is None:
            engine = get_pg_engine()
            ensure_collection_table(engine)
            store = get_vector_store(engine, get_embeddings())
        self._store = store
        self._generation_chain = generation_chain
        self._generation_model = generation_model

    def retrieve_top_k(self, query: str, k: int = 5, rerank: bool = True) -> list[ScoredChunk]:
        """Run vector search; if rerank=True, then cross-encoder rerank to k.

        The reranker oversamples — we ask the base retriever for 4k candidates
        (capped at 24, the dossier's "small corpus" upper bound for K=6
        reranked from 24) so the cross-encoder has more than top-K to choose
        from. With rerank=False, K is honoured directly by the vector search.
        """
        if not rerank:
            return retrieve(self._store, query, k=k)

        # Oversample to give the reranker room.
        candidate_k = min(max(4 * k, k + 5), 24)
        base = self._store.as_retriever(search_kwargs={"k": candidate_k})
        composed = compose_with_reranker(base, top_n=k)
        rerank_docs = composed.invoke(query)
        # ContextualCompressionRetriever drops scores; we recover them by re-running
        # similarity_search to align on metadata and produce ScoredChunk shape.
        # Cheap because pgvector already cached the candidate set.
        all_scored = retrieve(self._store, query, k=candidate_k)
        by_chunk_id = {c.chunk_id: c for c in all_scored}
        out: list[ScoredChunk] = []
        for doc in rerank_docs:
            # Same Pattern-B derivation as retrieval._derive_chunk_id — keeps the
            # alignment key consistent across the bi-encoder and the reranker.
            chunk_id = _derive_chunk_id(doc.metadata or {})
            if chunk_id and chunk_id in by_chunk_id:
                out.append(by_chunk_id[chunk_id])
        log.info("rag.lc.pipeline.retrieve", k=k, rerank=True, returned=len(out))
        return out

    def generate_bullets(self, job_description: str, k: int = 5, rerank: bool = True) -> str:
        """End-to-end: retrieve → optional rerank → generate bullets.

        The retrieval step is the same call `retrieve_top_k` exposes, so the
        benchmark can score retrieval and generation independently from the
        same pipeline object.
        """
        chunks = self.retrieve_top_k(job_description, k=k, rerank=rerank)
        chain = self._generation_chain or build_chain(model_name=self._generation_model)
        achievements = format_achievements(chunks)
        result = chain.invoke(
            {
                "job_description": job_description,
                "achievements": achievements,
                "k": len(chunks),
            }
        )
        log.info(
            "rag.lc.pipeline.generate",
            k=k,
            rerank=rerank,
            chunk_count=len(chunks),
            bullet_chars=len(result),
        )
        return result


__all__ = ["RagPipeline", "compose_with_reranker", "compose_without_reranker"]
