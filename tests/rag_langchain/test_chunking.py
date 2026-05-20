"""Tests for LangChain Document construction from Achievement."""

from pathlib import Path
from uuid import uuid4

import pytest

from jmi.models.achievement import Achievement
from jmi.rag_langchain.chunking import (
    SECTION_ORDER,
    chunk_achievement,
    chunk_achievement_sliding,
    chunk_achievements,
    sliding_window_splitter,
)


def _make_achievement(
    title: str = "Built a real-time payment matcher",
    context: str = "Worked at a fintech with 50M monthly transactions.",
    approach: str = "Designed a sliding-window state machine over Kafka.",
    impact: str = "Throughput 12k/sec, 99.99% match rate.",
    lessons: str = "Idempotency keys must be deterministic across retries.",
) -> Achievement:
    return Achievement(
        id=uuid4(),
        title=title,
        source_path=Path("subdir/achievement.md"),
        skills=["distributed-systems"],
        tech_stack=["kafka", "python"],
        seniority_relevance=["mid"],
        impact_metrics=["12k tps"],
        keywords=["payments"],
        context=context,
        approach=approach,
        impact=impact,
        lessons=lessons,
    )


class TestChunkAchievementPerSection:
    def test_emits_four_documents_for_full_achievement(self) -> None:
        achievement = _make_achievement()
        docs = chunk_achievement(achievement)
        assert len(docs) == 4
        assert {d.metadata["section"] for d in docs} == set(SECTION_ORDER)

    def test_chunk_index_matches_section_order(self) -> None:
        achievement = _make_achievement()
        docs = chunk_achievement(achievement)
        # Sorted by chunk_index, the sections must match SECTION_ORDER exactly.
        sorted_docs = sorted(docs, key=lambda d: int(d.metadata["chunk_index"]))
        sections = [d.metadata["section"] for d in sorted_docs]
        assert tuple(sections) == SECTION_ORDER

    def test_page_content_starts_with_header(self) -> None:
        achievement = _make_achievement(title="Quant Options Pricer")
        docs = chunk_achievement(achievement)
        for d in docs:
            label = d.metadata["section"].capitalize()
            if d.metadata["section"] == "lessons":
                label = "Lessons"
            expected_prefix = f"[Quant Options Pricer — {label}]"
            assert d.page_content.startswith(expected_prefix)

    def test_metadata_carries_required_keys(self) -> None:
        achievement = _make_achievement()
        docs = chunk_achievement(achievement)
        for d in docs:
            assert d.metadata["achievement_id"] == str(achievement.id)
            assert d.metadata["title"] == achievement.title
            assert d.metadata["section"] in SECTION_ORDER
            assert isinstance(d.metadata["chunk_index"], int)

    def test_empty_section_is_dropped(self) -> None:
        achievement = _make_achievement(lessons="   ")
        docs = chunk_achievement(achievement)
        assert len(docs) == 3
        assert all(d.metadata["section"] != "lessons" for d in docs)

    def test_all_empty_sections_yields_no_documents(self) -> None:
        achievement = _make_achievement(context="", approach="", impact="", lessons="")
        # The Achievement validator allows empty body fields, so chunker just returns [].
        docs = chunk_achievement(achievement)
        assert docs == []

    def test_chunk_achievements_flattens(self) -> None:
        a1 = _make_achievement(title="One")
        a2 = _make_achievement(title="Two")
        docs = chunk_achievements([a1, a2])
        assert len(docs) == 8  # 4 per achievement


class TestSlidingWindowChunker:
    @pytest.fixture
    def long_achievement(self) -> Achievement:
        # ~400 char body per section so a 1024/256 splitter yields multiple windows.
        body = "lorem ipsum dolor sit amet consectetur adipiscing elit. " * 10
        return _make_achievement(
            title="Long Story",
            context=body,
            approach=body,
            impact=body,
            lessons=body,
        )

    def test_sliding_window_yields_at_least_one_chunk(self, long_achievement: Achievement) -> None:
        docs = chunk_achievement_sliding(long_achievement)
        assert len(docs) >= 1

    def test_sliding_window_metadata_section_marks_full(
        self, long_achievement: Achievement
    ) -> None:
        docs = chunk_achievement_sliding(long_achievement)
        assert all(d.metadata["section"] == "full" for d in docs)

    def test_sliding_window_chunk_indices_are_dense(self, long_achievement: Achievement) -> None:
        docs = chunk_achievement_sliding(long_achievement)
        indices = [int(d.metadata["chunk_index"]) for d in docs]
        assert indices == list(range(len(docs)))

    def test_smaller_chunk_size_yields_more_chunks(self, long_achievement: Achievement) -> None:
        small = sliding_window_splitter(chunk_size=128, chunk_overlap=32)
        big = sliding_window_splitter(chunk_size=2048, chunk_overlap=128)
        small_docs = chunk_achievement_sliding(long_achievement, small)
        big_docs = chunk_achievement_sliding(long_achievement, big)
        assert len(small_docs) > len(big_docs)
