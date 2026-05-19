"""Tests for the Obsidian Markdown + frontmatter parser, on synthetic files."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from jmi.sources.obsidian.parser import AchievementParseError, to_achievement

_VALID = """\
---
type: achievement
title: IMC Prosperity 4
skills:
  - trading
tech_stack:
  - Python
seniority_relevance:
  - junior
impact_metrics:
  - "top 5%"
keywords:
  - competition
---

## Context

A trading competition.

## Approach

An agentic loop.

## Impact

Placed well.

## What I learned

Tradeoffs matter.
"""


def _path() -> Path:
    return Path("_meta/career/achievements/sample.md")


def test_parses_a_valid_achievement() -> None:
    achievement = to_achievement(_VALID, source_path=_path())
    assert achievement is not None
    assert achievement.title == "IMC Prosperity 4"
    assert achievement.skills == ["trading"]
    assert achievement.tech_stack == ["Python"]
    assert achievement.seniority_relevance == ["junior"]
    assert achievement.context == "A trading competition."
    assert achievement.approach == "An agentic loop."
    assert achievement.impact == "Placed well."
    assert achievement.lessons == "Tradeoffs matter."


def test_no_frontmatter_returns_none() -> None:
    assert to_achievement("# Just a note\n\nbody", source_path=_path()) is None


def test_non_achievement_type_returns_none() -> None:
    text = "---\ntype: meeting-note\ntitle: Standup\n---\n\nbody"
    assert to_achievement(text, source_path=_path()) is None


def test_type_match_is_case_insensitive() -> None:
    text = "---\ntype: Achievement\ntitle: Cased\n---\n\n## Context\n\nx"
    achievement = to_achievement(text, source_path=_path())
    assert achievement is not None
    assert achievement.title == "Cased"


def test_missing_body_section_defaults_to_empty() -> None:
    text = "---\ntype: achievement\ntitle: Minimal\n---\n\n## Context\n\nonly context"
    achievement = to_achievement(text, source_path=_path())
    assert achievement is not None
    assert achievement.context == "only context"
    assert achievement.approach == ""
    assert achievement.impact == ""
    assert achievement.lessons == ""


def test_unrecognised_section_is_ignored() -> None:
    text = (
        "---\ntype: achievement\ntitle: T\n---\n\n"
        "## Context\n\nctx\n\n## Notes\n\nignored\n\n## Impact\n\nimp"
    )
    achievement = to_achievement(text, source_path=_path())
    assert achievement is not None
    assert achievement.context == "ctx"
    assert achievement.impact == "imp"


def test_malformed_yaml_raises_parse_error() -> None:
    text = "---\ntype: achievement\ntitle: [unclosed\n---\n\nbody"
    with pytest.raises(AchievementParseError):
        to_achievement(text, source_path=_path())


def test_achievement_missing_title_raises_validation_error() -> None:
    text = "---\ntype: achievement\n---\n\n## Context\n\nx"
    with pytest.raises(ValidationError):
        to_achievement(text, source_path=_path())
