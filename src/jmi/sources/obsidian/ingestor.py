"""Ingest an Obsidian vault: walk Markdown files, parse achievements, upsert.

The H1 path sandbox (S-1) lives here — every candidate file is resolved and
checked for containment before it is opened. Logging follows S-2: file paths
and counts only, never achievement body content. See ADR-0014.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import structlog
from pydantic import ValidationError

from jmi.models.achievement import Achievement
from jmi.sources.obsidian.parser import AchievementParseError, to_achievement

log = structlog.get_logger(__name__)


class PathTraversalError(Exception):
    """A candidate file resolved to a location outside the vault root."""


@dataclass
class IngestStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0
    rejected: int = 0


class AchievementWriter(Protocol):
    """The slice of AchievementRepository the ingestor needs (ADR-0012)."""

    def get_by_source_path(self, source_path: str) -> Achievement | None: ...

    def add(self, item: Achievement) -> Achievement: ...

    def update(self, item: Achievement) -> Achievement: ...


def _resolve_within(root: Path, candidate: Path) -> Path:
    """Resolve `candidate` and assert it stays within `root` (H1 / S-1).

    Resolves symlinks and `..`, then raises PathTraversalError if the result is
    not contained by `root` — so a file outside the vault is never opened.
    """
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise PathTraversalError(f"{candidate} escapes the vault root")
    return resolved


def ingest_vault(repo: AchievementWriter, vault_path: Path) -> IngestStats:
    """Walk `vault_path` for achievement Markdown files and upsert them.

    A file is an achievement when its frontmatter carries `type: achievement`;
    other `.md` files are skipped. Existing rows are matched by vault-relative
    source path and updated in place; new ones are inserted.
    """
    root = vault_path.resolve()
    stats = IngestStats()
    for candidate in sorted(root.rglob("*.md")):
        try:
            resolved = _resolve_within(root, candidate)
        except PathTraversalError:
            log.warning("achievement.ingest.rejected", path=str(candidate))
            stats.rejected += 1
            continue

        relative = resolved.relative_to(root)
        try:
            text = resolved.read_text(encoding="utf-8")
            achievement = to_achievement(text, source_path=relative)
        except (OSError, UnicodeDecodeError, AchievementParseError, ValidationError) as exc:
            log.warning("achievement.ingest.invalid", path=str(relative), error=type(exc).__name__)
            stats.invalid += 1
            continue

        if achievement is None:
            stats.skipped += 1
            continue
        _upsert(repo, achievement, stats)

    log.info(
        "achievement.ingest.done",
        inserted=stats.inserted,
        updated=stats.updated,
        skipped=stats.skipped,
        invalid=stats.invalid,
        rejected=stats.rejected,
    )
    return stats


def _upsert(repo: AchievementWriter, parsed: Achievement, stats: IngestStats) -> None:
    """Insert a new achievement, or update an existing one matched by source path."""
    existing = repo.get_by_source_path(str(parsed.source_path))
    if existing is None:
        repo.add(parsed)
        stats.inserted += 1
        return
    merged = parsed.model_copy(
        update={
            "id": existing.id,
            "created_at": existing.created_at,
            "updated_at": datetime.now(UTC),
        }
    )
    repo.update(merged)
    stats.updated += 1
