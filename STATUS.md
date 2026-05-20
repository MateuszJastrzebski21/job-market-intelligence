# Worktree B — STATUS (final, post-recovery)

**Started:** 2026-05-20 01:42 local
**Finalised:** 2026-05-20 ~19:xx local (after 3 hard-recoveries)
**Branch:** `feat/phase3-pr3.2-B`
**Operator:** asleep at session start; supervising live by recovery time.

## Final commit log (top → bottom = newest → oldest)

| Commit | Task | Description |
| --- | --- | --- |
| `faaea70` | T11 fix prep | PATTERN B chunk_id + smoke-blocking pinpoints (4 fixes) |
| `2bd3e22` | T9 | docs(adr): ADR-0015b draft (Status: Proposed) |
| `27bdde5` | T8 | feat(rag-lc): end-to-end RagPipeline |
| `fc7fcef` | T7 | feat(rag-lc): LCEL generation chain with ChatAnthropic |
| `f5ec70c` | T6 | feat(rag-lc): cross-encoder reranker |
| `95bb866` | T5 | feat(rag-lc): top-K retriever wrapping PGVectorStore |
| `d03f388` | T4 | feat(rag-lc): PGVectorStore + separate collection table |
| `1ab1b1d` | T3 | feat(rag-lc): HuggingFaceEmbeddings adapter (BGE-small) |
| `628cbbc` | T2 | feat(rag-lc): per-section LangChain chunker |
| `0c80341` | T1 | build(rag-lc): pin langchain 0.3.x stack |
| `8370969` | (main) | (base) fix(privacy): generic placeholders |

## Final task status

| Task | Status |
| --- | --- |
| T1 — LangChain deps | ✓ DONE |
| T2 — Chunker (per-section + sliding) | ✓ DONE |
| T3 — Embedder (BGE-small via HF wrapper) | ✓ DONE |
| T4 — PGVectorStore + `langchain_achievement_embeddings` | ✓ DONE |
| T5 — Retriever | ✓ DONE |
| T6 — Reranker (CrossEncoderReranker + bge-reranker-base) | ✓ DONE |
| T7 — Generation (LCEL + ChatAnthropic) | ✓ DONE |
| T8 — End-to-end RagPipeline | ✓ DONE |
| T9 — ADR-0015b draft | ✓ DONE |
| T10 — Legacy PGVector port | ✗ SKIPPED (finalize-mode anti-goal) |
| T11 — 5 smoke samples | _see MINI-REPORT_ |

## Quality gates at HEAD (`faaea70`)

- `uv run pytest -q` → **206 passed** (45 new LangChain unit tests + 161 baseline preserved)
- `uv run mypy src/` → **0 errors** in 60 source files
- `uv run ruff check src/ tests/` → clean
- `uv run pre-commit run --all-files` → 8/8 pass

## BLOCKERS encountered (full list in MINI-REPORT.md)

1. API ECONNRESET after T8 — recovered, T1-T8 preserved on disk
2. Transient DNS failure to huggingface.co during first smoke run
3. PGVectorStore metadata schema (langchain_id is column not metadata) — fixed via PATTERN B
4. `init_vectorstore_table(overwrite_existing=False)` raises on duplicate — fixed (D4)
5. Empty `ANTHROPIC_API_KEY` already in shell env defeated `setdefault` — fixed
6. 3× hard recoveries — each cost ~15 min context rebuild, no work lost

## DECISIONS RECONSIDER (full details in MINI-REPORT.md)

- D1 — pgvector pin downgraded `>=0.4.2` → `>=0.3.6,<0.5`
- D2 — separate `langchain_achievement_embeddings` table (chunk content duplicated ~120 KB)
- D3 — PATTERN B chunk_id = `f"{slug}::{section}"` derived at query time
- D4 — tolerant `ensure_collection_table` (catch DuplicateTable as success)
- D5 — `SentenceTransformersCrossEncoder` instead of `langchain-community.HuggingFaceCrossEncoder`

## Confirmation: no `git push` ever ran

`git log --oneline origin/feat/phase3-pr3.2-B` errors — no remote tracking ref exists.
