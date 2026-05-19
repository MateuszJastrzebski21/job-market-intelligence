"""Achievement domain model — the Phase 3 RAG retrieval corpus.

See ADR-0014 and docs/phase3-design-constraints.md (H1) for the schema and the
security rationale behind path handling, logging, and storage separation.
"""

import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

SeniorityRelevance = Literal["junior", "mid", "senior"]


def slugify(value: str) -> str:
    """Return a lowercase ASCII slug: diacritics stripped, non-alphanumeric runs to '-'."""
    ascii_only = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    out: list[str] = []
    prev_dash = False
    for ch in ascii_only.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


class Achievement(BaseModel):
    """A personal career achievement parsed from an Obsidian vault Markdown file.

    Mirrors the JobPosting domain model, but holds the operator's own career
    history — so it is bound by the H1 security constraints recorded in ADR-0014.
    """

    model_config = ConfigDict(frozen=False, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    source_path: Path
    skills: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    seniority_relevance: list[SeniorityRelevance] = Field(default_factory=list)
    impact_metrics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    context: str
    approach: str
    impact: str
    lessons: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        """URL-safe identifier derived from the title; carries the table's UNIQUE."""
        return slugify(self.title)

    @field_validator("source_path")
    @classmethod
    def _reject_traversal(cls, value: Path) -> Path:
        # Defense-in-depth. The primary H1/S-1 containment gate runs in the
        # Obsidian ingestor, which resolves each path before opening the file.
        if value.is_absolute():
            raise ValueError("source_path must be vault-relative, not absolute")
        if ".." in value.parts:
            raise ValueError("source_path must not contain '..'")
        return value
