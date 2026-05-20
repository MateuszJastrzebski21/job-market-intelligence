"""LangChain retriever bound to PGVectorStore.

PGVectorStore exposes `as_retriever(search_kwargs={"k": K})`, returning a
`BaseRetriever` whose `invoke(query)` runs the bi-encoder similarity_search.
For parity with Worktree A's `CustomRetriever.retrieve(...) -> list[ScoredChunk]`,
this module wraps the LangChain retriever and surfaces scores from the
`similarity_search_with_score` API (PGVectorStore returns L2-or-cosine distance
based on the configured `DistanceStrategy`; default is cosine distance).

What LangChain hides here: the SQL operator (`<=>` for cosine distance), the
HNSW/IVFFlat index choice, the `EXPLAIN` plan — all behind `similarity_search`.
Mirrors the ADR-0015b §5 observability finding.

Security (S-2): logs ids and counts, never `chunk_text`.
"""

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from langchain_postgres import PGVectorStore

log = structlog.get_logger(__name__)


class ScoredChunk(BaseModel):
    """Chunk + retrieval score in the public interface mirrored from Worktree A.

    `score` semantics: higher = closer. PGVectorStore returns distance from
    `similarity_search_with_score` (lower distance = closer match); we convert
    by `score = 1 - distance` for cosine — bounded in [0, 1] for normalized
    embeddings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    achievement_id: str
    chunk_index: int
    section: str
    chunk_text: str
    score: float


def _distance_to_score(distance: float) -> float:
    return 1.0 - float(distance)


def retrieve(store: "PGVectorStore", query: str, k: int = 5) -> list[ScoredChunk]:
    """Retrieve top-K chunks for a query using PGVectorStore's similarity search.

    `store` is the bound PGVectorStore from `ingest.get_vector_store`. Score
    direction is normalised to "higher = better" so the result ordering matches
    Worktree A's contract.
    """
    raw = store.similarity_search_with_score(query, k=k)
    results: list[ScoredChunk] = []
    for doc, distance in raw:
        metadata = doc.metadata or {}
        results.append(
            ScoredChunk(
                chunk_id=str(metadata.get("langchain_id", "")),
                achievement_id=str(metadata.get("achievement_id", "")),
                chunk_index=int(metadata.get("chunk_index", -1)),
                section=str(metadata.get("section", "unknown")),
                chunk_text=doc.page_content,
                score=_distance_to_score(distance),
            )
        )
    log.info(
        "rag.lc.retrieve.done",
        k=k,
        returned=len(results),
        query_len=len(query),
    )
    return results
