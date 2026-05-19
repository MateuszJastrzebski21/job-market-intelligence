"""Domain ↔ ORM mapper tests for AchievementRepository.

Scope: the in-process Pydantic ↔ SQLAlchemy mapper round trip, mirroring
tests/storage/test_jobs_repo_nullable.py. DB-backed repository integration is
exercised end to end by the `jmi ingest-achievements` verification step.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from jmi.db.models import AchievementORM
from jmi.models.achievement import Achievement
from jmi.storage.achievements import _achievement_to_domain, _achievement_to_orm


def _make_achievement(**overrides: object) -> Achievement:
    defaults: dict[str, object] = {
        "title": "Volatility Surface Construction",
        "source_path": Path("_meta/career/achievements/vol.md"),
        "skills": ["quant", "modelling"],
        "tech_stack": ["Python", "NumPy"],
        "seniority_relevance": ["junior", "mid"],
        "impact_metrics": ["featured by a YouTube channel"],
        "keywords": ["volatility", "options"],
        "context": "ctx",
        "approach": "app",
        "impact": "imp",
        "lessons": "les",
    }
    defaults.update(overrides)
    return Achievement(**defaults)  # type: ignore[arg-type]


def test_to_orm_copies_columns() -> None:
    achievement = _make_achievement()
    orm = _achievement_to_orm(achievement)
    assert orm.id == achievement.id
    assert orm.title == achievement.title
    assert orm.slug == achievement.slug
    assert orm.tech_stack == ["Python", "NumPy"]
    assert orm.seniority_relevance == ["junior", "mid"]


def test_to_orm_stores_source_path_as_string() -> None:
    orm = _achievement_to_orm(_make_achievement())
    assert isinstance(orm.source_path, str)
    assert orm.source_path == "_meta/career/achievements/vol.md"


def test_domain_orm_domain_round_trip_is_lossless() -> None:
    original = _make_achievement()
    restored = _achievement_to_domain(_achievement_to_orm(original))
    assert restored == original


def test_to_domain_rebuilds_a_path_object() -> None:
    restored = _achievement_to_domain(_achievement_to_orm(_make_achievement()))
    assert isinstance(restored.source_path, Path)
    assert restored.source_path == Path("_meta/career/achievements/vol.md")


def test_to_domain_recomputes_slug_and_ignores_stored_value() -> None:
    orm = AchievementORM(
        id=uuid4(),
        title="Backend Java at a Fintech",
        slug="stale-slug-that-should-be-ignored",
        source_path="_meta/career/achievements/java.md",
        skills=[],
        tech_stack=[],
        seniority_relevance=[],
        impact_metrics=[],
        keywords=[],
        context="c",
        approach="a",
        impact="i",
        lessons="l",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    restored = _achievement_to_domain(orm)
    assert restored.slug == "backend-java-at-a-fintech"
