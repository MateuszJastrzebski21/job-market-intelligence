"""Chunk → embed → persist pipeline for ``achievement_embeddings`` (T3).

A pure-function orchestrator that the CLI ``jmi rag-embed`` and the tests both
call. The pipeline:

1. Pull each ``Achievement`` from ``AchievementRepository``.
2. Run the per-section ``chunk_achievement`` chunker (T1).
3. Embed every chunk via the ``CustomEmbedder`` (T2).
4. Replace prior embeddings via ``AchievementEmbeddingRepository`` (idempotent).

The embedder is injected so tests can pass a deterministic fake and so the
multilingual mini-experiment (T10) can swap it. Logging follows H7/O-4
naming (``rag.ingest.done``) and H1/S-2 — only counts/ids, never chunk body.
"""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict, Field

from jmi.models.achievement import Achievement
from jmi.rag.chunking import chunk_achievement
from jmi.storage.achievement_embeddings import ChunkRow

log = structlog.get_logger(__name__)


class EmbedderLike(Protocol):
    """The embedder shape ingest depends on (mirrors ``CustomEmbedder``).

    A ``Protocol`` not an ``ABC`` so future embedders (e.g. T10 multilingual)
    can satisfy it structurally without an explicit base class.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class AchievementReader(Protocol):
    """The read side of ``AchievementRepository`` the ingest needs."""

    def get(self, id: UUID) -> Achievement | None: ...
    def list_all(self, limit: int = 100, offset: int = 0) -> list[Achievement]: ...


class EmbeddingWriter(Protocol):
    """The write side of ``AchievementEmbeddingRepository`` the ingest needs."""

    def replace_for_achievement(self, achievement_id: UUID, chunks: list[ChunkRow]) -> int: ...


class IngestStats(BaseModel):
    """Per-run summary returned to the CLI."""

    model_config = ConfigDict(extra="forbid")

    achievements_processed: int = Field(ge=0)
    achievements_skipped: int = Field(ge=0)  # zero chunks → nothing to write
    chunks_written: int = Field(ge=0)


def ingest_embeddings(
    achievements_repo: AchievementReader,
    embeddings_repo: EmbeddingWriter,
    embedder: EmbedderLike,
    *,
    achievement_ids: Iterable[UUID] | None = None,
    list_batch_size: int = 1000,
) -> IngestStats:
    """Embed every selected achievement and replace its rows in storage.

    When ``achievement_ids`` is ``None``, every achievement returned by
    ``list_all`` is processed. The corpus is small (target ~50), so a single
    ``list_all`` call with a generous ``list_batch_size`` is fine — no
    pagination needed. The function is idempotent: running it twice on the same
    inputs produces the same database state (the writer replaces prior chunks).
    """
    targets = list(_load_achievements(achievements_repo, achievement_ids, list_batch_size))

    processed = 0
    skipped = 0
    chunks_written = 0

    for achievement in targets:
        chunks = chunk_achievement(achievement)
        if not chunks:
            log.info(
                "rag.ingest.skipped",
                achievement_id=str(achievement.id),
                slug=achievement.slug,
                reason="no non-empty sections",
            )
            skipped += 1
            continue
        vectors = embedder.embed_documents([c.text_for_embedding for c in chunks])
        if len(vectors) != len(chunks):
            # Should not happen — embed_documents preserves length — but log
            # and skip rather than write a partial record.
            log.error(
                "rag.ingest.embed.mismatch",
                achievement_id=str(achievement.id),
                chunk_count=len(chunks),
                vector_count=len(vectors),
            )
            skipped += 1
            continue
        rows = [
            ChunkRow(
                achievement_id=c.achievement_id,
                chunk_index=c.chunk_index,
                chunk_text=c.chunk_text,
                embedding=v,
            )
            for c, v in zip(chunks, vectors, strict=True)
        ]
        n = embeddings_repo.replace_for_achievement(achievement.id, rows)
        chunks_written += n
        processed += 1
        log.info(
            "rag.ingest.achievement.done",
            achievement_id=str(achievement.id),
            slug=achievement.slug,
            chunk_count=n,
        )

    log.info(
        "rag.ingest.done",
        processed=processed,
        skipped=skipped,
        chunks_written=chunks_written,
    )
    return IngestStats(
        achievements_processed=processed,
        achievements_skipped=skipped,
        chunks_written=chunks_written,
    )


def _load_achievements(
    repo: AchievementReader,
    achievement_ids: Iterable[UUID] | None,
    list_batch_size: int,
) -> list[Achievement]:
    if achievement_ids is None:
        return repo.list_all(limit=list_batch_size)
    out: list[Achievement] = []
    for aid in achievement_ids:
        item = repo.get(aid)
        if item is None:
            log.warning("rag.ingest.unknown_id", achievement_id=str(aid))
            continue
        out.append(item)
    return out
