"""Tests for the Obsidian vault ingestor, including the H1/S-1 path sandbox.

The ingestor is exercised against a synthetic vault under tmp_path with an
in-memory fake repository — no database, no real Obsidian vault.
"""

from pathlib import Path

import pytest

from jmi.models.achievement import Achievement
from jmi.sources.obsidian.ingestor import PathTraversalError, _resolve_within, ingest_vault

_ACHIEVEMENT = """\
---
type: achievement
title: {title}
---

## Context

ctx
"""


class _FakeRepo:
    """In-memory AchievementWriter for offline ingestor tests."""

    def __init__(self) -> None:
        self.by_path: dict[str, Achievement] = {}

    def get_by_source_path(self, source_path: str) -> Achievement | None:
        return self.by_path.get(source_path)

    def add(self, item: Achievement) -> Achievement:
        self.by_path[str(item.source_path)] = item
        return item

    def update(self, item: Achievement) -> Achievement:
        self.by_path[str(item.source_path)] = item
        return item


def _write(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_ACHIEVEMENT.format(title=title), encoding="utf-8")


def test_ingests_achievement_files(tmp_path) -> None:
    _write(tmp_path / "career" / "a.md", "First")
    _write(tmp_path / "career" / "b.md", "Second")
    repo = _FakeRepo()

    stats = ingest_vault(repo, tmp_path)

    assert stats.inserted == 2
    assert stats.skipped == 0
    assert len(repo.by_path) == 2


def test_skips_non_achievement_markdown(tmp_path) -> None:
    _write(tmp_path / "a.md", "Real")
    (tmp_path / "README.md").write_text("# Readme\n\nnot an achievement", encoding="utf-8")
    repo = _FakeRepo()

    stats = ingest_vault(repo, tmp_path)

    assert stats.inserted == 1
    assert stats.skipped == 1


def test_reingest_updates_in_place(tmp_path) -> None:
    md = tmp_path / "a.md"
    _write(md, "Original Title")
    repo = _FakeRepo()
    ingest_vault(repo, tmp_path)

    md.write_text(_ACHIEVEMENT.format(title="Edited Title"), encoding="utf-8")
    stats = ingest_vault(repo, tmp_path)

    assert stats.inserted == 0
    assert stats.updated == 1
    assert len(repo.by_path) == 1
    assert next(iter(repo.by_path.values())).title == "Edited Title"


def test_invalid_achievement_is_counted(tmp_path) -> None:
    (tmp_path / "bad.md").write_text("---\ntype: achievement\n---\n\nbody", encoding="utf-8")
    repo = _FakeRepo()

    stats = ingest_vault(repo, tmp_path)

    assert stats.invalid == 1
    assert stats.inserted == 0


def test_symlink_escaping_the_vault_is_rejected(tmp_path) -> None:
    # H1 / S-1: a symlink inside the vault pointing outside must be rejected, not opened.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(_ACHIEVEMENT.format(title="Secret"), encoding="utf-8")

    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault / "real.md", "Real")
    (vault / "escape.md").symlink_to(outside / "secret.md")

    repo = _FakeRepo()
    stats = ingest_vault(repo, vault)

    assert stats.rejected == 1
    assert stats.inserted == 1
    assert "Secret" not in {a.title for a in repo.by_path.values()}


def test_resolve_within_accepts_a_contained_path(tmp_path) -> None:
    root = tmp_path.resolve()
    target = root / "f.md"
    target.write_text("x", encoding="utf-8")

    assert _resolve_within(root, target) == target


def test_resolve_within_rejects_a_parent_escape(tmp_path) -> None:
    root = (tmp_path / "vault").resolve()
    root.mkdir()

    with pytest.raises(PathTraversalError):
        _resolve_within(root, root / ".." / "elsewhere.md")
