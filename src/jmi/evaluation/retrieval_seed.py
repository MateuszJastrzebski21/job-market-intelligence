"""Pydantic models for the RAG retrieval ground-truth seed (audit H5 / E-2).

Validates `docs/ground_truth/rag_retrieval_seed.json` — the golden set scored by
`evaluation.benchmark` against any retriever satisfying the Pipeline protocol.

## Chunk id format — `{achievement_key}::{section}`

The schema doc (`docs/ground_truth/rag_retrieval_seed_schema.md`) calls the
identifier "a row in the `achievement_embeddings` table". In practice the row
uuids change on re-ingest and the embeddings table is empty until PR-3.2
worktree A's ingest pass populates it — neither suits a durable seed. The
durable identifier is a content-addressable pair:

- `achievement_key` — the achievement's vault file stem (no extension), e.g.
  `bus-punctuality-neural-network`. Stable across re-ingests because the
  ingestor's upsert key is `source_path` (ADR-0014).
- `section` — one of `context`, `approach`, `impact`, `lessons` — the four
  fields the Obsidian parser produces (`src/jmi/sources/obsidian/parser.py`).

Both the custom (worktree A) and the LangChain (worktree B) retrievers MUST
return chunk ids in this canonical form so the benchmark scores comparable
outputs. The helper `chunk_id_for(source_path, section)` enforces the format.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

QueryLanguage = Literal["en", "pl"]
Section = Literal["context", "approach", "impact", "lessons"]
_SECTIONS: tuple[Section, ...] = ("context", "approach", "impact", "lessons")


def chunk_id_for(source_path: str | Path, section: str) -> str:
    """Return the canonical seed-compatible chunk id for one section of one file.

    Format: `{stem}::{section}`. `stem` is the vault-relative file's basename
    without the `.md` extension. Both retrievers MUST produce ids in this shape.
    """
    if section not in _SECTIONS:
        raise ValueError(f"section must be one of {_SECTIONS}, got {section!r}")
    stem = Path(source_path).stem
    if not stem:
        raise ValueError(f"cannot derive achievement key from empty stem: {source_path!r}")
    return f"{stem}::{section}"


def parse_chunk_id(chunk_id: str) -> tuple[str, Section]:
    """Inverse of `chunk_id_for` — split a canonical id back into (key, section)."""
    key, sep, section = chunk_id.partition("::")
    if not sep or not key or section not in _SECTIONS:
        raise ValueError(f"not a canonical chunk id: {chunk_id!r}")
    # The `section in _SECTIONS` check above narrows `section` to Section.
    return key, section


class RagSeedEntry(BaseModel):
    """One labelled query in the retrieval golden set.

    `extra="forbid"` so a typo'd field in the JSON fails loudly. `query_language`
    extends the original schema doc (it specified only `query` and
    `relevant_chunk_ids`) to support worktree A's Polish-routing experiment.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    query_language: QueryLanguage = "en"
    relevant_chunk_ids: list[str] = Field(min_length=1)
    graded_relevance: dict[str, float] | None = None
    notes: str | None = None

    @field_validator("relevant_chunk_ids")
    @classmethod
    def _validate_chunk_ids(cls, value: list[str]) -> list[str]:
        for cid in value:
            # delegates format checking to parse_chunk_id; raises on invalid.
            parse_chunk_id(cid)
        if len(value) != len(set(value)):
            raise ValueError("relevant_chunk_ids contains duplicates")
        return value

    @model_validator(mode="after")
    def _graded_must_cover_relevant(self) -> "RagSeedEntry":
        # Per schema doc: when both are present, `relevant_chunk_ids` is a
        # subset of `graded_relevance` keys.
        if self.graded_relevance is None:
            return self
        missing = set(self.relevant_chunk_ids) - set(self.graded_relevance)
        if missing:
            raise ValueError(
                f"graded_relevance must cover all relevant_chunk_ids; missing: {sorted(missing)}"
            )
        return self


class RagSeedFile(BaseModel):
    """Top-level shape of `rag_retrieval_seed.json`."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    entries: list[RagSeedEntry] = Field(min_length=1)

    @field_validator("entries")
    @classmethod
    def _entry_ids_unique(cls, value: list[RagSeedEntry]) -> list[RagSeedEntry]:
        ids = [e.id for e in value]
        if len(ids) != len(set(ids)):
            raise ValueError("seed entry ids must be unique")
        return value


_FILE_ADAPTER: TypeAdapter[RagSeedFile] = TypeAdapter(RagSeedFile)


def parse_seed(raw: str | bytes) -> RagSeedFile:
    """Validate raw JSON into a `RagSeedFile`."""
    return _FILE_ADAPTER.validate_json(raw)


def load_seed(path: str | Path) -> RagSeedFile:
    """Read and validate the seed JSON file at `path`."""
    return parse_seed(Path(path).read_bytes())


def chunk_id_universe(entries: Sequence[RagSeedEntry]) -> set[str]:
    """Return every chunk id referenced by any entry — the corpus-relevance pool."""
    universe: set[str] = set()
    for entry in entries:
        universe.update(entry.relevant_chunk_ids)
    return universe
