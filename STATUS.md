# Worktree B — STATUS

**Started:** 2026-05-20 01:42 local
**Branch:** `feat/phase3-pr3.2-B`
**Operator:** sleeping; overnight session, write-with-trace only — NO pushes.

## Time budget

Hard stop **07:00 local**. Currently 01:42. Effective budget: ~5h coding + 20m
mini-report + 10m morning-buffer.

## Tasks completed

(none yet — setup phase)

## Tasks in progress

- Setup (PLAN.md ✓, STATUS.md in flight)

## BLOCKERS

(none)

## DECISIONS taken without operator input

### D1 (RECONSIDER) — pgvector pin downgraded to `>=0.3.6,<0.5`

`langchain-postgres 0.0.17` (latest in the 0.0.x line) requires `pgvector<0.4`,
so adding it forced a downgrade of the project's pgvector pin (was `>=0.4.2`).
Existing JMI code only imports `pgvector.sqlalchemy.Vector` — stable across
0.3.x and 0.4.x — so behaviour does not change, but Worktree A's branch will
inherit the same pin once these PRs merge sequentially. **RECONSIDER** in
ADR-0015b: the operator may prefer to wait for langchain-postgres to release
a pgvector-0.4-compatible line before merging Worktree B to main.

### D2 (RECONSIDER) — Worktree B uses a separate `langchain_achievement_embeddings` table

PGVectorStore from `langchain-postgres` owns its schema (`langchain_id` UUID PK,
`content` text, `embedding` vector, `langchain_metadata` JSONB). It does NOT
accept JMI's existing `achievement_embeddings` schema with its typed
`achievement_id` FK + `chunk_index` constraint without writing a custom
VectorStore subclass — at which point Worktree B would no longer be
"LangChain idiomatic." I chose **Option A** from the orchestrator's spec:
a sibling table `langchain_achievement_embeddings` on the same database,
populated via `PGEngine.init_vectorstore_table` and `PGVectorStore.create_sync`.

**Cost.** Each chunk is now stored twice (once per implementation) for the
duration of the comparison — ~80 chunks × 384 × 4 bytes ≈ 120 KB total,
negligible.

**Why this is the right call for the comparison.** The dossier explicitly
flags schema ownership as LangChain's biggest abstraction bite (§5). Making
the bite visible — two side-by-side tables in the same DB — is the comparison
material ADR-0015 (synthesis) needs. Forcing a unified schema would hide it.

**RECONSIDER** if a follow-up PR wants Worktree B to consume Worktree A's
canonical chunks via a read-only adapter, side-stepping the duplication.

## File-by-file commit log

- `pyproject.toml`, `uv.lock` — T1, pin langchain 0.3.x stack + relax pgvector
- `PLAN.md`, `STATUS.md` — overnight audit trail
- `src/jmi/rag_langchain/__init__.py` — T2, package marker
- `src/jmi/rag_langchain/chunking.py` — T2, per-section LangChain Documents + sliding-window splitter
- `tests/rag_langchain/test_chunking.py` — T2, 11 chunking tests pass
- `src/jmi/rag_langchain/embedding.py` — T3, HuggingFaceEmbeddings adapter (BGE-small-en-v1.5)
- `tests/rag_langchain/test_embedding.py` — T3, 4 embedding-adapter tests pass
- `src/jmi/rag_langchain/ingest.py` — T4, PGEngine + PGVectorStore wiring + deterministic ids
- `tests/rag_langchain/test_ingest.py` — T4, 7 ingest tests pass

## Notes

- Baseline `uv run pytest -q` = 161 passed in B worktree before any change.
- Branches `feat/phase3-pr3.2-A` and `feat/phase3-pr3.2-B` were pre-existing
  at main HEAD (8370969). Worktrees `jmi-pr32-A` and `jmi-pr32-B` directories
  pre-existed too — registered via `git worktree`. Confirmed via
  `git worktree list`. Treating these as the canonical worktrees for the
  overnight session.
- Sibling sessions: A claimed first (013917), B claimed by me (013947), C
  presumably claimed third. Cross-worktree coordination only via reading
  sibling STATUS.md when needed.
