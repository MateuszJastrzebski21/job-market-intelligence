# Worktree B — LangChain RAG Implementation — PLAN

**Started:** 2026-05-20 01:42 local
**Branch:** `feat/phase3-pr3.2-B` (off `main` @ 8370969)
**Goal:** Reimplement Worktree A's RAG pipeline using LangChain 0.3.x primitives so
operator can compare custom-vs-framework on the same corpus and ground truth.

## Fixed decisions (from orchestrator)

- **LangChain stack:** 0.3.x — pin explicit versions:
  - `langchain ~= 0.3` (chains)
  - `langchain-core ~= 0.3`
  - `langchain-postgres ~= 0.0.14` (PGVectorStore, NOT deprecated PGVector)
  - `langchain-huggingface ~= 0.1`
  - `langchain-anthropic ~= 0.3`
- **Vectorstore:** PGVectorStore from `langchain-postgres` (current API).
- **Embedding model:** `BAAI/bge-small-en-v1.5` via `HuggingFaceEmbeddings` (same as A — 384-dim).
- **Reranker:** `BAAI/bge-reranker-base` via `HuggingFaceCrossEncoder` + `CrossEncoderReranker`
  composed into `ContextualCompressionRetriever`.
- **Generation:** `ChatAnthropic(claude-opus-4-7)` via LCEL chain composition.
- **Mirror Worktree A's public interface:** `RagPipeline.retrieve_top_k(...)` and
  `generate_bullets(...)` so the benchmark harness can swap implementations.

## Open decision — to resolve in T4 (schema strategy)

Per dossier §5 and orchestrator T4 note: `PGVectorStore` from `langchain-postgres` owns
its own schema (`langchain_pg_collection`, `langchain_pg_embedding`). It cannot share
the existing typed `achievement_embeddings` table with its FK to `achievements`.

### Two options the orchestrator names

- **A.** Create a separate table `langchain_achievement_embeddings` with PGVectorStore's
  expected schema. Document divergence.
- **B.** Extend the existing table with whatever columns LangChain requires. Risky:
  LangChain owns the schema, so this leaks framework state into the typed table.

### Preferred (subject to schema inspection during T4)

**Option A — separate `langchain_achievement_embeddings` collection.** Rationale:
1. The dossier explicitly flags schema ownership as LangChain's biggest abstraction
   bite. A separate collection makes the bite *visible* — the comparison story is
   honest.
2. The custom-side achievement_embeddings table has `FK(achievement_id) → achievements`,
   `chunk_index INT`, `chunk_text TEXT`, `embedding Vector(384)`, plus `created_at`
   and a `UNIQUE(achievement_id, chunk_index)`. PGVectorStore stores `id`, `document`,
   `cmetadata JSONB`, `embedding vector(N)`, `collection_id` — different shape, no FK.
3. **No risk of cross-side data corruption.** A LangChain ingest pass cannot smear
   over custom-side rows or vice versa. Both sides can co-exist on the same DB.
4. Forcing the custom-side schema onto LangChain would mean a custom `VectorStore`
   subclass — at which point this worktree is no longer "LangChain idiomatic."

The trade-off: the *same* DB now holds two copies of each chunk's embedding (one in
each table). Tolerable: ~80 chunks × 384 floats × 4 bytes = ~120 KB total. Logged
as a DECISION RECONSIDER in STATUS.md.

## Task ordering

T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T11 → T10 (legacy mini-experiment last,
since main-branch work is the priority and T10 is comparison material).

**Smoke check (T11)** depends on having a runnable end-to-end pipeline (post-T8).

**ADR-0015b (T9)** can be drafted in parallel with T7/T8 once the schema decision
crystallises.

## Quality gates at every commit

- `uv run pytest -q` — no regressions (baseline 161)
- `uv run mypy src/` — 0 errors
- `uv run ruff check src/ tests/` — clean
- `uv run pre-commit run --all-files` — 8/8 hooks

## Security constraints (H1, S-2)

- Never log achievement body text (chunk_text). Log structures, ids, paths, counts.
- LangChain `verbose=True` and LangSmith tracing are DISABLED — they would leak
  chunk text into stderr.
- Smoke-check outputs (T11) are local files — operator owns them; chunk text is
  allowed there. Same rule as Worktree A's smoke outputs.

## Files to create

```
src/jmi/rag_langchain/
  __init__.py
  chunking.py       # T2 — per-section LangChain Documents + sliding-window splitter
  embedding.py      # T3 — HuggingFaceEmbeddings(bge-small-en-v1.5) adapter
  ingest.py         # T4/T5 — PGVectorStore + collection setup + ingest loop
  retrieval.py      # T5 — LangChain retriever
  reranking.py      # T6 — CrossEncoderReranker + ContextualCompressionRetriever
  generation.py     # T7 — LCEL chain with ChatAnthropic
  pipeline.py       # T8 — public RagPipeline class

src/jmi/db/migrations/versions/<rev>_langchain_pgvectorstore_tables.py
  # If PGVectorStore creates its own tables on init, NO migration needed.
  # If we need to bootstrap the langchain_pg_* tables, this migration owns it.

docs/adr/0015b-langchain-rag-implementation.md   # T9

experiments/pr32-smoke-check/langchain/{slug}.md  # T11 × 5

tests/rag_langchain/
  __init__.py
  test_chunking.py
  test_embedding.py
  test_ingest.py
  test_retrieval.py
  test_reranking.py
  test_generation.py
  test_pipeline.py
```

## What I am NOT doing in this worktree

- Re-running the custom-side benchmark (Worktree C owns the harness).
- Writing the comparison ADR-0015 (Worktree C owns synthesis).
- Adjusting the existing `achievement_embeddings` schema in any way.
- Pushing or opening a PR (write-with-trace).
