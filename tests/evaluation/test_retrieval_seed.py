"""Unit tests for the RAG retrieval ground-truth seed validator.

The seed JSON is the contract between the operator's labels (chunks → queries)
and the benchmark harness; mistakes here invalidate every retrieval metric, so
the validator is paranoid by design (extra='forbid', subset checks, unique-id
checks). These tests exercise both the happy path and the rejection paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from jmi.evaluation.retrieval_seed import (
    RagSeedEntry,
    RagSeedFile,
    chunk_id_for,
    chunk_id_universe,
    load_seed,
    parse_chunk_id,
    parse_seed,
)

# Repository root — tests/, src/, docs/ live as siblings. `parents[2]` walks
# `test_retrieval_seed.py -> evaluation -> tests -> <repo root>`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED_FILE = _REPO_ROOT / "docs" / "ground_truth" / "rag_retrieval_seed.json"


# ---------- chunk_id_for / parse_chunk_id ----------


def test_chunk_id_for_basic() -> None:
    assert chunk_id_for("bus-punctuality-neural-network.md", "context") == (
        "bus-punctuality-neural-network::context"
    )


def test_chunk_id_for_strips_path_and_extension() -> None:
    full = "_meta/career/achievements/jmi-flagship-project.md"
    assert chunk_id_for(full, "approach") == "jmi-flagship-project::approach"


def test_chunk_id_for_accepts_pathlib_path() -> None:
    assert chunk_id_for(Path("a/b/c.md"), "impact") == "c::impact"


def test_chunk_id_for_rejects_unknown_section() -> None:
    with pytest.raises(ValueError, match="section must be one of"):
        chunk_id_for("foo.md", "summary")  # type: ignore[arg-type]


def test_chunk_id_for_rejects_empty_stem() -> None:
    with pytest.raises(ValueError, match="empty stem"):
        chunk_id_for("", "context")


def test_parse_chunk_id_round_trip() -> None:
    for section in ("context", "approach", "impact", "lessons"):
        cid = chunk_id_for("foo-bar.md", section)
        key, parsed_section = parse_chunk_id(cid)
        assert key == "foo-bar"
        assert parsed_section == section


def test_parse_chunk_id_rejects_unknown_section() -> None:
    with pytest.raises(ValueError, match="not a canonical chunk id"):
        parse_chunk_id("foo::summary")


def test_parse_chunk_id_rejects_missing_separator() -> None:
    with pytest.raises(ValueError, match="not a canonical chunk id"):
        parse_chunk_id("foo-context")


# ---------- RagSeedEntry ----------


def _entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "q1",
        "query": "Python ML engineer",
        "query_language": "en",
        "relevant_chunk_ids": ["foo::context", "bar::approach"],
    }
    base.update(overrides)
    return base


def test_seed_entry_accepts_minimal_required_fields() -> None:
    entry = RagSeedEntry.model_validate(_entry())
    assert entry.id == "q1"
    assert entry.query_language == "en"
    assert entry.graded_relevance is None
    assert entry.notes is None


def test_seed_entry_defaults_query_language_to_en() -> None:
    payload = _entry()
    payload.pop("query_language")
    entry = RagSeedEntry.model_validate(payload)
    assert entry.query_language == "en"


def test_seed_entry_accepts_polish() -> None:
    entry = RagSeedEntry.model_validate(_entry(query_language="pl"))
    assert entry.query_language == "pl"


def test_seed_entry_rejects_unknown_language() -> None:
    with pytest.raises(ValidationError):
        RagSeedEntry.model_validate(_entry(query_language="de"))


def test_seed_entry_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RagSeedEntry.model_validate(_entry(typo="oops"))


def test_seed_entry_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        RagSeedEntry.model_validate(_entry(query=""))


def test_seed_entry_rejects_empty_relevant_chunk_ids() -> None:
    with pytest.raises(ValidationError):
        RagSeedEntry.model_validate(_entry(relevant_chunk_ids=[]))


def test_seed_entry_rejects_duplicate_chunk_ids() -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        RagSeedEntry.model_validate(_entry(relevant_chunk_ids=["foo::context", "foo::context"]))


def test_seed_entry_rejects_malformed_chunk_id() -> None:
    with pytest.raises(ValidationError):
        RagSeedEntry.model_validate(_entry(relevant_chunk_ids=["foo-context"]))


def test_seed_entry_graded_relevance_must_cover_relevant_ids() -> None:
    payload = _entry(graded_relevance={"foo::context": 1.0})  # missing bar::approach
    with pytest.raises(ValidationError, match="graded_relevance must cover"):
        RagSeedEntry.model_validate(payload)


def test_seed_entry_graded_relevance_superset_ok() -> None:
    # graded_relevance may include extra ids beyond relevant — only the subset
    # check is required.
    payload = _entry(
        graded_relevance={"foo::context": 1.0, "bar::approach": 0.5, "baz::impact": 0.25}
    )
    entry = RagSeedEntry.model_validate(payload)
    assert entry.graded_relevance is not None
    assert "baz::impact" in entry.graded_relevance


# ---------- RagSeedFile ----------


def test_seed_file_minimal() -> None:
    payload = {"version": "1", "entries": [_entry()]}
    seed = RagSeedFile.model_validate(payload)
    assert seed.version == "1"
    assert len(seed.entries) == 1


def test_seed_file_rejects_empty_entries() -> None:
    with pytest.raises(ValidationError):
        RagSeedFile.model_validate({"version": "1", "entries": []})


def test_seed_file_rejects_duplicate_entry_ids() -> None:
    e1 = _entry(id="q1")
    e2 = _entry(id="q1", query="different text")
    with pytest.raises(ValidationError, match="unique"):
        RagSeedFile.model_validate({"version": "1", "entries": [e1, e2]})


def test_seed_file_rejects_unknown_top_level_field() -> None:
    payload = {"version": "1", "entries": [_entry()], "extra": "bad"}
    with pytest.raises(ValidationError):
        RagSeedFile.model_validate(payload)


def test_parse_seed_from_bytes() -> None:
    payload = {"version": "1", "entries": [_entry()]}
    raw = json.dumps(payload).encode("utf-8")
    seed = parse_seed(raw)
    assert seed.entries[0].id == "q1"


# ---------- The actual on-disk seed file ----------


def test_real_seed_file_parses() -> None:
    """The shipped JSON must validate. Catches schema drift at commit time."""
    seed = load_seed(_SEED_FILE)
    assert seed.version == "1"
    assert len(seed.entries) >= 10, "audit H5 / E-2 requires ≥10 entries before MVP"


def test_real_seed_file_has_15_entries() -> None:
    """Worktree C T1 spec: 15 queries — 5 single + 5 cross + 3 PL + 2 edge."""
    seed = load_seed(_SEED_FILE)
    assert len(seed.entries) == 15


def test_real_seed_file_has_three_polish_queries() -> None:
    seed = load_seed(_SEED_FILE)
    polish = [e for e in seed.entries if e.query_language == "pl"]
    assert len(polish) == 3


def test_real_seed_file_every_chunk_id_is_canonical() -> None:
    """Every referenced chunk id parses cleanly — catches typos in the labels."""
    seed = load_seed(_SEED_FILE)
    for entry in seed.entries:
        for cid in entry.relevant_chunk_ids:
            parse_chunk_id(cid)  # raises on malformed; this is the assertion


def test_real_seed_file_chunk_ids_reference_known_vault_files() -> None:
    """Each chunk's achievement-key must match an actual vault file basename.

    Hand-coded so the test does not depend on a live vault path — those file
    basenames are the durable identifiers (ADR-0014's `source_path` upsert key).
    """
    expected_keys = {
        "bus-punctuality-neural-network",
        "car-price-prediction-dsc-pjatk",
        "engineering-thesis-btc-signal-prediction",
        "hackyeah-2025-transport-tracker",
        "imc-prosperity-4-agentic-autoresearch",
        "jmi-flagship-project",
        "pjatk-data-science-club-membership",
        "quantfolio-javafx-portfolio-simulator",
        "railway-logistics-simulation",
        "red-ocean-junior-java-developer",
        "volatility-surface-coding-jesus-feature",
    }
    seed = load_seed(_SEED_FILE)
    referenced_keys = {parse_chunk_id(cid)[0] for cid in chunk_id_universe(seed.entries)}
    unknown = referenced_keys - expected_keys
    assert not unknown, f"seed references unknown achievement keys: {sorted(unknown)}"


def test_chunk_id_universe_returns_unique_ids() -> None:
    entries = [
        RagSeedEntry.model_validate(_entry(id="q1", relevant_chunk_ids=["a::context"])),
        RagSeedEntry.model_validate(
            _entry(id="q2", relevant_chunk_ids=["a::context", "b::approach"])
        ),
    ]
    universe = chunk_id_universe(entries)
    assert universe == {"a::context", "b::approach"}
