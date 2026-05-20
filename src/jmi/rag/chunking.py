"""Per-section chunking for the Achievement RAG corpus (ADR-0015a §Chunking).

The Obsidian parser (PR-3.1) already split each achievement into four labelled
fields — ``context`` / ``approach`` / ``impact`` / ``lessons``. This module
emits one ``Chunk`` per non-empty section, with a static ``[Title — Section]``
header prepended for free Contextual-Retrieval-style grounding (the dossier
§1.recommendation). The header is part of ``text_for_embedding`` and of the
stored ``chunk_text`` so retrieval results display the same payload that was
embedded.

Pure functions — no I/O, no embedding model. Trivially unit-testable.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from jmi.models.achievement import Achievement

Section = Literal["context", "approach", "impact", "lessons"]

# Fixed section order so ``chunk_index`` is stable across re-ingests of the
# same achievement (ADR-0014 UNIQUE constraint on (achievement_id, chunk_index)).
_SECTION_ORDER: tuple[Section, ...] = ("context", "approach", "impact", "lessons")

# Display label for the prepended header. Kept distinct from the field name so
# the embedded text reads naturally to a hiring-manager-style query.
_SECTION_DISPLAY: dict[Section, str] = {
    "context": "Context",
    "approach": "Approach",
    "impact": "Impact",
    "lessons": "What I learned",
}


class Chunk(BaseModel):
    """A single embeddable slice of an Achievement.

    ``chunk_text`` is what gets persisted to ``achievement_embeddings.chunk_text``
    and what retrieval returns to the generator. ``text_for_embedding`` is what
    the embedder consumes. They are intentionally the same string today —
    splitting the field surfaces the invariant and leaves room for a future
    embedder-only prefix (e.g. bge's ``"Represent this sentence for searching: "``
    query instruction) without changing the stored payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    achievement_id: UUID
    chunk_index: int = Field(ge=0)
    section: Section
    chunk_text: str = Field(min_length=1)
    text_for_embedding: str = Field(min_length=1)


def _format_header(title: str, section: Section) -> str:
    """Build the ``[Title — Section]`` header line (em-dash, single line)."""
    return f"[{title} — {_SECTION_DISPLAY[section]}]"


def _section_body(achievement: Achievement, section: Section) -> str:
    """Pull the named section body off the Achievement model, trimmed."""
    value: str = getattr(achievement, section)
    return value.strip()


def chunk_achievement(achievement: Achievement) -> list[Chunk]:
    """Return one Chunk per non-empty section of ``achievement``.

    Sections are emitted in the fixed order ``context → approach → impact →
    lessons``. Empty sections are skipped — ``chunk_index`` is the **emit
    position**, so a missing section shifts the indices of later sections down.
    A vault is small and re-ingest is idempotent (PR-3.1 upsert on ``source_path``),
    so the dense-index policy is fine; the alternative — keeping section→index
    stable across achievements — wastes index space and complicates the
    UNIQUE(achievement_id, chunk_index) replay in ``ingest.ingest_embeddings``.

    Returns an empty list when *every* section is empty. The caller is
    responsible for whatever that means at the corpus level (skip vs warn).
    """
    chunks: list[Chunk] = []
    emit_index = 0
    for section in _SECTION_ORDER:
        body = _section_body(achievement, section)
        if not body:
            continue
        header = _format_header(achievement.title, section)
        text = f"{header}\n\n{body}"
        chunks.append(
            Chunk(
                achievement_id=achievement.id,
                chunk_index=emit_index,
                section=section,
                chunk_text=text,
                text_for_embedding=text,
            )
        )
        emit_index += 1
    return chunks
