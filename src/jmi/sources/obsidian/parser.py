"""Parse Obsidian vault Markdown files into Achievement domain models.

Pure functions — no file I/O, no DB. The ingestor owns file reading, the H1
path sandbox, and persistence. See ADR-0014.
"""

from pathlib import Path
from typing import Any

import yaml

from jmi.models.achievement import Achievement

_ACHIEVEMENT_TYPE = "achievement"
_FENCE = "---"

# Markdown `## ` heading (lower-cased) -> Achievement body field name.
_SECTION_FIELDS = {
    "context": "context",
    "approach": "approach",
    "impact": "impact",
    "what i learned": "lessons",
}


class AchievementParseError(Exception):
    """A file is meant to be an achievement but cannot be parsed into one."""


def to_achievement(text: str, *, source_path: Path) -> Achievement | None:
    """Parse one Markdown document into an Achievement.

    Returns None when the file is not an achievement — no YAML frontmatter, or
    its `type` is not `achievement` — so the caller can skip it. Raises
    AchievementParseError or pydantic.ValidationError when the file is meant to
    be an achievement but is malformed.
    """
    frontmatter, body = _split_frontmatter(text)
    if str(frontmatter.get("type", "")).lower() != _ACHIEVEMENT_TYPE:
        return None
    sections = _split_sections(body)
    return Achievement(
        title=frontmatter.get("title"),
        source_path=source_path,
        skills=frontmatter.get("skills") or [],
        tech_stack=frontmatter.get("tech_stack") or [],
        seniority_relevance=frontmatter.get("seniority_relevance") or [],
        impact_metrics=frontmatter.get("impact_metrics") or [],
        keywords=frontmatter.get("keywords") or [],
        context=sections.get("context", ""),
        approach=sections.get("approach", ""),
        impact=sections.get("impact", ""),
        lessons=sections.get("lessons", ""),
    )


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a document into (frontmatter mapping, body).

    Frontmatter is a leading YAML block fenced by `---` lines. Returns an empty
    mapping when there is no frontmatter, the block is unterminated, or the
    YAML is not a mapping. Raises AchievementParseError on malformed YAML.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() != _FENCE:
            continue
        body = "\n".join(lines[i + 1 :])
        try:
            loaded = yaml.safe_load("\n".join(lines[1:i]))
        except yaml.YAMLError as exc:
            raise AchievementParseError(f"invalid YAML frontmatter: {exc}") from exc
        return (loaded, body) if isinstance(loaded, dict) else ({}, body)
    return {}, text


def _split_sections(body: str) -> dict[str, str]:
    """Map the recognised `## ` headings of a body to Achievement body fields.

    Headings absent from `_SECTION_FIELDS` (and their text), and any preamble
    before the first heading, are ignored. Heading match is case-insensitive.
    """
    sections: dict[str, str] = {}
    field: str | None = None
    buffer: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if field is not None:
                sections[field] = "\n".join(buffer).strip()
            field = _SECTION_FIELDS.get(line[3:].strip().lower())
            buffer = []
        elif field is not None:
            buffer.append(line)
    if field is not None:
        sections[field] = "\n".join(buffer).strip()
    return sections
