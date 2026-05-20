"""Tests for the chunk → embed → persist ingest pipeline (T3).

The pipeline is exercised against in-memory fakes that satisfy the inline
Protocols on ``rag.ingest`` — the same pattern Phase 1–2 repositories use
(ADR-0012). No DB, no real model.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from jmi.models.achievement import Achievement
from jmi.rag.ingest import ingest_embeddings
from jmi.storage.achievement_embeddings import ChunkRow


class _FakeAchievementRepo:
    def __init__(self, items: list[Achievement]) -> None:
        self._items = {a.id: a for a in items}

    def get(self, id: UUID) -> Achievement | None:
        return self._items.get(id)

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Achievement]:
        return list(self._items.values())[offset : offset + limit]


class _FakeEmbeddingRepo:
    def __init__(self) -> None:
        self.store: dict[UUID, list[ChunkRow]] = {}

    def replace_for_achievement(self, achievement_id: UUID, chunks: list[ChunkRow]) -> int:
        self.store[achievement_id] = list(chunks)
        return len(chunks)


class _FakeEmbedder:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
        self.calls: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        # Deterministic per-text vector: a one-hot-ish that lets us assert
        # length and ordering without depending on a real model.
        return [[float((hash(t) >> i) & 1) for i in range(self.dim)] for t in texts]


def _achievement(
    *,
    title: str = "Sample Achievement",
    path: str = "achievements/sample.md",
    context: str = "C.",
    approach: str = "A.",
    impact: str = "I.",
    lessons: str = "L.",
) -> Achievement:
    return Achievement(
        id=uuid4(),
        title=title,
        source_path=Path(path),
        context=context,
        approach=approach,
        impact=impact,
        lessons=lessons,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_writes_one_chunk_per_section_for_each_achievement() -> None:
    a = _achievement()
    b = _achievement(title="Other", path="achievements/other.md")
    repo = _FakeAchievementRepo([a, b])
    embed_repo = _FakeEmbeddingRepo()
    stats = ingest_embeddings(repo, embed_repo, _FakeEmbedder())
    assert stats.achievements_processed == 2
    assert stats.achievements_skipped == 0
    assert stats.chunks_written == 8
    assert len(embed_repo.store[a.id]) == 4
    assert len(embed_repo.store[b.id]) == 4


def test_chunk_text_persisted_includes_header() -> None:
    a = _achievement(title="My Project")
    repo = _FakeAchievementRepo([a])
    embed_repo = _FakeEmbeddingRepo()
    ingest_embeddings(repo, embed_repo, _FakeEmbedder())
    texts = [c.chunk_text for c in embed_repo.store[a.id]]
    assert texts[0].startswith("[My Project — Context]")
    assert texts[3].startswith("[My Project — What I learned]")


def test_embedding_shape_persisted() -> None:
    a = _achievement()
    repo = _FakeAchievementRepo([a])
    embed_repo = _FakeEmbeddingRepo()
    ingest_embeddings(repo, embed_repo, _FakeEmbedder(dim=384))
    for row in embed_repo.store[a.id]:
        assert row.embedding is not None
        assert len(row.embedding) == 384


def test_idempotent_rerun_overwrites_prior_chunks() -> None:
    a = _achievement()
    repo = _FakeAchievementRepo([a])
    embed_repo = _FakeEmbeddingRepo()
    ingest_embeddings(repo, embed_repo, _FakeEmbedder())
    first = list(embed_repo.store[a.id])
    ingest_embeddings(repo, embed_repo, _FakeEmbedder())
    second = embed_repo.store[a.id]
    # Same texts, same indices — but ChunkRow ``id`` rolls each call, so equal
    # by content not by row identity.
    assert [r.chunk_text for r in first] == [r.chunk_text for r in second]
    assert [r.chunk_index for r in first] == [r.chunk_index for r in second]


def test_subset_by_achievement_ids() -> None:
    a = _achievement(title="A")
    b = _achievement(title="B", path="achievements/b.md")
    repo = _FakeAchievementRepo([a, b])
    embed_repo = _FakeEmbeddingRepo()
    stats = ingest_embeddings(repo, embed_repo, _FakeEmbedder(), achievement_ids=[a.id])
    assert stats.achievements_processed == 1
    assert a.id in embed_repo.store
    assert b.id not in embed_repo.store


def test_unknown_achievement_id_is_skipped_not_raised() -> None:
    a = _achievement()
    repo = _FakeAchievementRepo([a])
    embed_repo = _FakeEmbeddingRepo()
    ghost = uuid4()
    stats = ingest_embeddings(repo, embed_repo, _FakeEmbedder(), achievement_ids=[a.id, ghost])
    assert stats.achievements_processed == 1


def test_all_empty_achievement_is_counted_as_skipped() -> None:
    a = _achievement(context="", approach="", impact="", lessons="")
    repo = _FakeAchievementRepo([a])
    embed_repo = _FakeEmbeddingRepo()
    stats = ingest_embeddings(repo, embed_repo, _FakeEmbedder())
    assert stats.achievements_processed == 0
    assert stats.achievements_skipped == 1
    assert stats.chunks_written == 0
    assert embed_repo.store == {}


def test_chunk_index_matches_emit_position() -> None:
    a = _achievement(context="", approach="A.", impact="I.", lessons="L.")
    repo = _FakeAchievementRepo([a])
    embed_repo = _FakeEmbeddingRepo()
    ingest_embeddings(repo, embed_repo, _FakeEmbedder())
    indices = [r.chunk_index for r in embed_repo.store[a.id]]
    assert indices == [0, 1, 2]
