"""Per-section chunking of Achievements, emitted as LangChain Documents.

The corpus is already parsed into four named fields (`context` / `approach` / `impact`
/ `lessons`) by the Obsidian parser (PR-3.1). LangChain ships text splitters but they
consume raw markdown strings — for this corpus we skip the splitter and construct
Documents directly from the typed fields, which is the same per-section strategy as
Worktree A. The mini-experiment splitter (sliding window via
RecursiveCharacterTextSplitter) is also exposed here so ADR-0015b can compare both.

Each chunk carries a `[Title — Section]` header prepended to the body — the static
contextual-retrieval pattern from the dossier (§1, Anthropic's Contextual Retrieval),
free at zero LLM cost. Metadata is enough to round-trip back to the source achievement.

Security: no logging of chunk text. Logging is by id/section only.
"""

from collections.abc import Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from jmi.models.achievement import Achievement

# Stable ordering — chunk_index 0..3 maps to the four fields in this order. Same as
# Worktree A so the chunk_index of a (achievement_id, section) pair matches across
# implementations. Don't reorder without bumping the seed file's chunk ids.
SECTION_ORDER: tuple[str, ...] = ("context", "approach", "impact", "lessons")

# Heading the operator sees in the Obsidian vault for each field.
_SECTION_LABEL = {
    "context": "Context",
    "approach": "Approach",
    "impact": "Impact",
    "lessons": "Lessons",
}


def chunk_achievement(achievement: Achievement) -> list[Document]:
    """Split an Achievement into up to four per-section LangChain Documents.

    Empty sections are dropped (a section with no body has nothing to embed). The
    `page_content` is the contextual-retrieval-style `[Title — Section]\\n\\n<body>`
    string — what we feed the embedder. Metadata carries the keys the retriever and
    benchmark need: achievement_id (uuid string), chunk_index (0..3, position in
    SECTION_ORDER), section (one of SECTION_ORDER), title.
    """
    docs: list[Document] = []
    for index, section in enumerate(SECTION_ORDER):
        body = getattr(achievement, section)
        if not body or not body.strip():
            continue
        header = f"[{achievement.title} — {_SECTION_LABEL[section]}]"
        page_content = f"{header}\n\n{body.strip()}"
        docs.append(
            Document(
                page_content=page_content,
                metadata={
                    "achievement_id": str(achievement.id),
                    "chunk_index": index,
                    "section": section,
                    "title": achievement.title,
                },
            )
        )
    return docs


def chunk_achievements(achievements: Sequence[Achievement]) -> list[Document]:
    """Flatten chunk_achievement over a list of Achievements."""
    out: list[Document] = []
    for a in achievements:
        out.extend(chunk_achievement(a))
    return out


def sliding_window_splitter(
    chunk_size: int = 1024, chunk_overlap: int = 256
) -> RecursiveCharacterTextSplitter:
    """RecursiveCharacterTextSplitter configured for the sliding-window mini-experiment.

    Character-based (LangChain's only choice without an extra dep), so the size is in
    characters not tokens — a deliberate part of the comparison: a 256-token chunk
    is roughly 1024 chars for English, but this is approximate and the dossier notes
    it (§1d). Defaults match the dossier's mini-experiment knobs at a 4× scale-up to
    characters.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )


def chunk_achievement_sliding(
    achievement: Achievement,
    splitter: RecursiveCharacterTextSplitter | None = None,
) -> list[Document]:
    """Sliding-window variant — joins all four sections, then splits with overlap.

    Used by the mini-experiment branch only. Each chunk carries `chunk_index` (its
    position in the split output) and `section="full"` to mark the strategy. The
    same `[Title]` header is prepended per chunk so retrieval still has provenance.
    """
    splitter = splitter if splitter is not None else sliding_window_splitter()
    body_parts = [
        f"## Context\n{achievement.context.strip()}",
        f"## Approach\n{achievement.approach.strip()}",
        f"## Impact\n{achievement.impact.strip()}",
        f"## Lessons\n{achievement.lessons.strip()}",
    ]
    body = "\n\n".join(part for part in body_parts if part.strip().endswith(":") is False)
    pieces = splitter.split_text(body)
    docs: list[Document] = []
    for i, piece in enumerate(pieces):
        page_content = f"[{achievement.title}]\n\n{piece.strip()}"
        docs.append(
            Document(
                page_content=page_content,
                metadata={
                    "achievement_id": str(achievement.id),
                    "chunk_index": i,
                    "section": "full",
                    "title": achievement.title,
                },
            )
        )
    return docs
