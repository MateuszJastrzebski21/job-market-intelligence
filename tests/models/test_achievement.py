"""Pydantic contract tests for the Achievement domain model."""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from jmi.models.achievement import Achievement, slugify


def _make(**overrides: object) -> Achievement:
    defaults: dict[str, object] = {
        "title": "Test Achievement",
        "source_path": Path("_meta/career/achievements/test.md"),
        "context": "ctx",
        "approach": "app",
        "impact": "imp",
        "lessons": "les",
    }
    defaults.update(overrides)
    return Achievement(**defaults)  # type: ignore[arg-type]


def test_slug_is_computed_from_title() -> None:
    assert _make(title="Backend Java at a Fintech").slug == "backend-java-at-a-fintech"


def test_slugify_strips_polish_diacritics() -> None:
    assert slugify("Powierzchnia zmienności opcji") == "powierzchnia-zmiennosci-opcji"


def test_slugify_collapses_punctuation() -> None:
    assert slugify("Kraków — Project's Café & Co.!") == "krakow-project-s-cafe-co"


def test_slug_cannot_be_passed_to_constructor() -> None:
    # `slug` is a computed field — _achievement_to_domain relies on it not being settable.
    with pytest.raises(ValidationError):
        _make(slug="custom-slug")


def test_source_path_rejects_absolute() -> None:
    with pytest.raises(ValidationError):
        _make(source_path=Path("/etc/passwd"))


def test_source_path_rejects_parent_traversal() -> None:
    with pytest.raises(ValidationError):
        _make(source_path=Path("../../secrets.md"))


def test_source_path_accepts_clean_relative_path() -> None:
    achievement = _make(source_path=Path("_meta/career/achievements/x.md"))
    assert achievement.source_path == Path("_meta/career/achievements/x.md")


def test_seniority_relevance_accepts_known_values() -> None:
    achievement = _make(seniority_relevance=["junior", "mid", "senior"])
    assert achievement.seniority_relevance == ["junior", "mid", "senior"]


def test_seniority_relevance_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        _make(seniority_relevance=["expert"])


def test_title_rejects_empty_string() -> None:
    with pytest.raises(ValidationError):
        _make(title="")


def test_title_rejects_overlong_string() -> None:
    with pytest.raises(ValidationError):
        _make(title="x" * 201)


def test_list_fields_default_to_empty() -> None:
    achievement = _make()
    assert achievement.skills == []
    assert achievement.tech_stack == []
    assert achievement.seniority_relevance == []
    assert achievement.impact_metrics == []
    assert achievement.keywords == []


def test_timestamps_default_to_datetime() -> None:
    achievement = _make()
    assert isinstance(achievement.created_at, datetime)
    assert isinstance(achievement.updated_at, datetime)


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        _make(unexpected_field="nope")
