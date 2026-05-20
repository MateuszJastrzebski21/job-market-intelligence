"""Repository for chunk-level achievement embeddings (ADR-0014 ``achievement_embeddings``).

A thin domain ↔ ORM boundary mirroring ``AchievementRepository``: callers hand
Pydantic ``ChunkRow`` instances; SQLAlchemy stays behind the session. The
repo is owned by the RAG ingest pipeline (PR-3.2, T3) and the retriever (T4).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from jmi.db.models import AchievementEmbeddingORM


class ChunkRow(BaseModel):
    """One row of ``achievement_embeddings`` as a typed domain value.

    ``embedding`` is a ``list[float] | None`` to match the column nullability
    (PR-3.1 created the table embedding-nullable so the schema landed ahead of
    behaviour). Reads from the retriever always carry a non-None embedding.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    achievement_id: UUID
    chunk_index: int = Field(ge=0)
    chunk_text: str = Field(min_length=1)
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AchievementEmbeddingRepository:
    """Reads and writes ``achievement_embeddings`` rows.

    The write path is "delete then insert" keyed on ``achievement_id`` — chunk
    indices are dense from 0 (see ``rag.chunking._SECTION_ORDER``), so the
    cheapest way to keep ``UNIQUE(achievement_id, chunk_index)`` happy across
    re-ingests is to wipe and rewrite. The achievement vault is small; per-row
    upserts would not be cheaper and would surface ON CONFLICT details that do
    not earn their complexity here.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_achievement(
        self,
        achievement_id: UUID,
        chunks: list[ChunkRow],
    ) -> int:
        """Delete every chunk for ``achievement_id`` then insert ``chunks``.

        Returns the number of rows written. Caller commits the surrounding
        session — this method only flushes.
        """
        self._session.execute(
            delete(AchievementEmbeddingORM).where(
                AchievementEmbeddingORM.achievement_id == achievement_id
            )
        )
        for row in chunks:
            self._session.add(_chunk_to_orm(row))
        self._session.flush()
        return len(chunks)

    def list_for_achievement(self, achievement_id: UUID) -> list[ChunkRow]:
        """All chunks for one achievement, ordered by ``chunk_index``."""
        stmt = (
            select(AchievementEmbeddingORM)
            .where(AchievementEmbeddingORM.achievement_id == achievement_id)
            .order_by(AchievementEmbeddingORM.chunk_index)
        )
        return [_chunk_to_domain(o) for o in self._session.execute(stmt).scalars()]

    def count(self) -> int:
        """Total chunk count across all achievements."""
        return int(self._session.scalar(select(func.count(AchievementEmbeddingORM.id))) or 0)


def _chunk_to_orm(row: ChunkRow) -> AchievementEmbeddingORM:
    return AchievementEmbeddingORM(
        id=row.id,
        achievement_id=row.achievement_id,
        chunk_index=row.chunk_index,
        chunk_text=row.chunk_text,
        embedding=row.embedding,
        created_at=row.created_at,
    )


def _chunk_to_domain(o: AchievementEmbeddingORM) -> ChunkRow:
    return ChunkRow(
        id=o.id,
        achievement_id=o.achievement_id,
        chunk_index=o.chunk_index,
        chunk_text=o.chunk_text,
        embedding=list(o.embedding) if o.embedding is not None else None,
        created_at=o.created_at,
    )
