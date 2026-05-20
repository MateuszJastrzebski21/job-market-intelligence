"""Custom pgvector retriever (T4).

A thin wrapper around an explicit ``ORDER BY embedding <=> :q LIMIT :k`` query
against ``achievement_embeddings`` — kept visible on purpose so the LangChain
comparison (Worktree B) can point at "this is what ``similarity_search`` hides
from you" (dossier §5).

The retriever owns its embedder but not its session — the session is injected
per call so the caller controls the transaction. The result type carries an
explicit ``score`` (cosine *similarity* — 1 − distance) so a downstream
reranker (T5) and benchmark (Worktree C) can compare scores on the same scale.
"""

from typing import Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jmi.db.models import AchievementEmbeddingORM

log = structlog.get_logger(__name__)


class QueryEmbedder(Protocol):
    """The embedder shape the retriever depends on (mirrors ``CustomEmbedder``)."""

    def embed_query(self, text: str) -> list[float]: ...


class ScoredChunk(BaseModel):
    """One scored result row.

    ``score`` is cosine *similarity* in [-1.0, 1.0] (1.0 = identical direction).
    The DB returns cosine *distance* (``embedding <=> :q``); the retriever
    converts to similarity here so callers never have to remember which sign is
    "better."
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: UUID
    achievement_id: UUID
    chunk_index: int = Field(ge=0)
    chunk_text: str = Field(min_length=1)
    score: float


class CustomRetriever:
    """Embed query → cosine-similarity search → top-K ``ScoredChunk`` list.

    No reranking, no document-level rollup — composing them is T5/T6's job.
    """

    def __init__(self, embedder: QueryEmbedder) -> None:
        self._embedder = embedder

    def retrieve(self, session: Session, query: str, k: int = 5) -> list[ScoredChunk]:
        """Return the top ``k`` chunks by cosine similarity to ``query``.

        Returns fewer than ``k`` rows when the corpus is smaller than ``k``.
        Raises ``ValueError`` for ``k <= 0`` — the upstream API should treat a
        zero ``k`` as "do not retrieve" before calling.
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if not query.strip():
            log.warning("rag.retrieve.empty_query")
            return []
        vector = self._embedder.embed_query(query)
        # Cosine distance operator from pgvector. With L2-normalised inputs,
        # distance == 1 - similarity. The ORDER BY <-> ... LIMIT pattern is
        # the same pattern jmi.analytics.cluster uses, kept visible so the
        # framework comparison has a concrete "this is what's hidden" exhibit.
        distance_expr = AchievementEmbeddingORM.embedding.cosine_distance(vector)
        stmt = (
            select(AchievementEmbeddingORM, distance_expr.label("distance"))
            .where(AchievementEmbeddingORM.embedding.isnot(None))
            .order_by(distance_expr)
            .limit(k)
        )
        rows = session.execute(stmt).all()
        results: list[ScoredChunk] = []
        for orm, distance in rows:
            results.append(
                ScoredChunk(
                    chunk_id=orm.id,
                    achievement_id=orm.achievement_id,
                    chunk_index=orm.chunk_index,
                    chunk_text=orm.chunk_text,
                    score=float(1.0 - float(distance)),
                )
            )
        log.info(
            "rag.retrieve.done",
            k=k,
            returned=len(results),
            top_chunk_id=str(results[0].chunk_id) if results else None,
        )
        return results
