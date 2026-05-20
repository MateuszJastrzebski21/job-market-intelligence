# Worktree C — STATUS

**Started:** 2026-05-20 ~14:04 local (recovery from API timeout; original
orchestrator launched ~01:30).
**Branch:** `feat/phase3-pr3.2-C`
**Baseline:** main @ 8370969, 161 pytest green, mypy/ruff/pre-commit clean.

## Tasks completed

_(none yet)_

## Tasks in progress

- T1 — ground truth seed (starting now)

## BLOCKERS

_(none yet)_

## DECISIONS

- **D1 (RECONSIDER):** chunk ids in the ground-truth seed are synthetic and
  content-addressable, of the form `{achievement_slug}::{section}` — *not*
  `achievement_embeddings.id` uuids. Reasoning: (1) the table is empty at C's
  start, so I cannot bind to real ids; (2) re-ingest churns uuids, so even if
  populated they would not be durable; (3) both A and B can map their stored
  chunks to this id at eval time via `(achievement_slug, section)`. The
  benchmark harness reads chunk ids back from the retriever in the same shape.
  If the operator wants real uuids, the seed file is regenerable from
  `(achievement_id, chunk_index)` joins after A populates the table.

- **D2 (RECONSIDER — coordination):** the orphaned `B-claimed-...013941.txt`
  is mine from the pre-timeout attempt. I am not touching the `feat/phase3-pr3.2-B`
  worktree or the second-B session's work; my orphaned claim is harmless but I
  document it so the morning operator does not think two sessions are racing.

## File-by-file commit log

_(empty)_

## Next 30 min

T1 — write the Pydantic validator + the 15-query JSON file. Commit. Move to T2.
