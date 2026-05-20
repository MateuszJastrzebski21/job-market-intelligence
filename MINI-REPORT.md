# Worktree B — MINI-REPORT (overnight session, finalised post-recovery)

**Branch:** `feat/phase3-pr3.2-B`
**Base:** `main` @ `8370969`
**Session window:** 2026-05-20 01:42 → 2026-05-20 19:xx local (3 hard-recoveries from API/ECONNRESET).
**Mode:** dual-worktree overnight orchestrator, write-with-trace only — no pushes, no PRs.

## Status summary

| Task | Status | Commit |
| --- | --- | --- |
| T1 — Pin LangChain 0.3.x deps | DONE | `0c80341` |
| T2 — Per-section LangChain chunker + sliding-window splitter | DONE | `628cbbc` |
| T3 — `HuggingFaceEmbeddings` adapter for BGE-small-en-v1.5 | DONE | `1ab1b1d` |
| T4 — `PGVectorStore` on `langchain_achievement_embeddings` | DONE | `d03f388` |
| T5 — Top-K retriever wrapping `PGVectorStore` | DONE | `95bb866` |
| T6 — Cross-encoder reranker via `CrossEncoderReranker` | DONE | `f5ec70c` |
| T7 — LCEL generation chain with `ChatAnthropic` | DONE | `fc7fcef` |
| T8 — End-to-end `RagPipeline` mirroring Worktree A | DONE | `27bdde5` |
| T9 — ADR-0015b draft (`docs/adr/0015b-langchain-rag-implementation.md`) | DONE | `2bd3e22` |
| Smoke-driven fixes — PATTERN B chunk_id, env load, embedder kwarg, table create | DONE | `faaea70` |
| T10 — Legacy PGVector (`langchain-community`) port | **SKIPPED** | — |
| T11 — 5 smoke-check generation samples | **DONE** | `a3c2641` |

## T10 — explicitly skipped

Finalise-mode anti-goal. The legacy-PGVector mini-experiment is a comparison-only
exercise (the schema-collision story it would tell is already structurally visible
in ADR-0015b §4 via the sibling `langchain_achievement_embeddings` collection
table). With three recoveries eating the time budget, the operator's instruction
was explicit: T11 over T10.

If the operator wants T10 later, the branch off-point is `faaea70` (latest B
commit). The legacy port replaces:

- `langchain_postgres.PGVectorStore.create_sync` → `langchain_community.vectorstores.PGVector(connection=..., collection_name=..., embedding_function=...)`
- `langchain_postgres.PGEngine` → no equivalent — the legacy class takes a
  SQLAlchemy `Engine` or URL string directly.
- Schema: legacy `PGVector` creates `langchain_pg_collection` + `langchain_pg_embedding` tables itself; the dossier §5 "the sharpest lock-in finding" line lands directly.

That is roughly 1-2h of work on a quiet network and a 30-line `PORT-NOTES.md`.

## T11 — smoke-check generation samples — DONE

5 markdown files committed in `experiments/pr32-smoke-check/langchain/`:

1. AI Engineer (English) — `smoke-ai-engineer-english.md` (8.7 KB, 5 chunks, 1542 char bullets)
2. Junior Backend Java (Polish) — `smoke-junior-backend-java-polish.md` (7.3 KB, 5 chunks)
3. Quant Researcher (English) — `smoke-quant-researcher-english.md` (7.8 KB, 5 chunks)
4. ML Engineer (English) — `smoke-ml-engineer-english.md` (7.7 KB, 5 chunks, 1511 char bullets)
5. Data Engineer (Polish) — `smoke-data-engineer-polish.md` (7.6 KB, 5 chunks, 1664 char bullets)

Format per orchestrator spec: Input JD, Retrieved Chunks (top-5 with scores +
section + PATTERN B chunk_id), Generated Bullets, Notes (with operator-labeling
placeholders for grounded/partial/hallucinated).

Generation model: `claude-opus-4-7` via `langchain-anthropic`'s `ChatAnthropic`.
Reranker enabled (4×k oversample → top-5). Wall clock for all 5 samples on
warm-cache models: ~3-4 min.

Operator review path:

```
cd .claude/worktrees/jmi-pr32-B
ls experiments/pr32-smoke-check/langchain/
# Open each smoke-{slug}.md, fill in the Notes section labels.
```

Re-running the harness if the corpus changes:

```
uv run python experiments/pr32-smoke-check/langchain/run_langchain_smoke.py
```

The script is idempotent — it re-ingests the corpus into the LangChain
collection table (deterministic UUID5 ids) and overwrites the smoke files.

**Cross-worktree comparison.** Worktree A's matching samples should land in
`experiments/pr32-smoke-check/{slug}.md` (no `/langchain/` subdir). Both sets
use the same 5 JDs verbatim and the same K=5, rerank=on configuration, so
the operator can diff retrieval ordering and bullet wording directly.

## Quality gates

All four green at `HEAD = faaea70` (smoke-driven fixes commit):

- `uv run pytest -q` → **206 passed** (45 new in `tests/rag_langchain/`, 161 baseline preserved)
- `uv run mypy src/` → **0 errors** in 60 source files
- `uv run ruff check src/ tests/` → clean
- `uv run pre-commit run --all-files` → 8/8 hooks pass

## Decisions taken without operator input (RECONSIDER)

### D1 — pgvector pin downgraded to `>=0.3.6,<0.5`

`langchain-postgres 0.0.17` (latest 0.0.x) requires `pgvector<0.4`. Adding it
forced a project-wide pin downgrade from `>=0.4.2`. JMI only consumes
`pgvector.sqlalchemy.Vector` (stable across both major versions) so behaviour
is unchanged, but the downgrade is the "abstraction tax" the dossier predicted.

**RECONSIDER** when `langchain-postgres` ships a `pgvector>=0.4`-compatible
release.

### D2 — Worktree B uses a separate `langchain_achievement_embeddings` table

`PGVectorStore` owns its schema (`langchain_id` UUID PK, `content` text,
`embedding` vector, `langchain_metadata` JSONB) and cannot honour
`achievement_embeddings`' FK + UNIQUE invariants without a custom `VectorStore`
subclass — at which point Worktree B is no longer "LangChain idiomatic."

Chose the **sibling table** approach (orchestrator's option A). Both stacks
coexist on the same database; chunk content is duplicated (~120 KB total — 80
chunks × 384 × 4 bytes). The dossier-predicted schema-collision (§5) is now
*structurally visible* — two side-by-side tables in the same DB.

**RECONSIDER** if a follow-up PR wants Worktree B to read Worktree A's
canonical chunks via a read-only adapter, side-stepping the duplication.

### D3 — PATTERN B chunk_id derivation at query time

PGVectorStore does not persist deterministic `langchain_id` UUIDs into
`Document.metadata` — it stays on the PK column only. The first smoke run hit
this: `metadata.get("langchain_id")` returned `""` for every chunk → pipeline
rerank-recovery alignment failed → `returned=0`.

Fix: `retrieval._derive_chunk_id` computes `chunk_id = f"{slugify(title)}::{section}"`
at query time, matching the chunk_id convention used by Worktree A's
`CustomRetriever` and Worktree C's ground-truth seed. Backwards compatible —
tests that mock metadata with explicit `langchain_id` still honour it.

**RECONSIDER** in ADR-0015 (synthesis) — this format is now the *cross-worktree
convention* for chunk_ids and should be recorded as such (currently implicit).

### D4 — Tolerant `ensure_collection_table`

`PGEngine.init_vectorstore_table(overwrite_existing=False)` *raises* DuplicateTable
on second run rather than skipping (LangChain's docstring is misleading). The
ingest module now catches `ProgrammingError` whose `orig` is `DuplicateTable`
and treats it as success. Genuinely idempotent.

**RECONSIDER** — open a `langchain-postgres` issue documenting the API contract.

### D5 — Sentence-transformers CrossEncoder over `langchain-community.HuggingFaceCrossEncoder`

To avoid pulling `langchain-community` (~50 MB of unrelated stuff) just for one
class, Worktree B implements a tiny `SentenceTransformersCrossEncoder(BaseCrossEncoder)`
that wraps the already-installed `sentence_transformers.CrossEncoder`. Saved
one dependency at the cost of ~25 lines of adapter code.

**RECONSIDER** when T10 (legacy port) is done — that experiment WILL pull in
`langchain-community`, so the saved dependency may evaporate anyway.

## Blockers encountered

1. **API ECONNRESET after T8** — overnight session disconnected; resumed from
   commit `27bdde5` via second prompt. T1-T8 fully preserved on disk.

2. **DNS to huggingface.co intermittent during first smoke run** — `bge-reranker-base`
   never downloaded, all 5 samples failed. Resolved on retry.

3. **PGVectorStore metadata schema** — `langchain_id` is a column, not a metadata
   key. Diagnosed mid-smoke, fixed via PATTERN B (D3). Not predictable from
   `langchain-postgres` docstrings — only surfaced under live data.

4. **`init_vectorstore_table(overwrite_existing=False)` actually raises on
   duplicate** — surfaced on the second smoke attempt. Fixed in D4.

5. **Empty `ANTHROPIC_API_KEY` in inherited shell environment** — `os.environ.setdefault`
   skipped because the key was present (but empty). Fixed: only overwrite when
   the existing value is empty/unset.

6. **3× hard recoveries** — each cost ~15 min of context-rebuild. None of the
   recoveries lost committed work (write-with-trace held).

## Operator next steps (first 30 min)

1. **Review ADR-0015b** (`docs/adr/0015b-langchain-rag-implementation.md`) — every
   non-trivial decision in Worktree B has a section there with the trade-off.
2. **Inspect smoke samples** in `experiments/pr32-smoke-check/langchain/` and
   label each bullet `grounded / partial / hallucinated` in the Notes section.
3. **Compare side-by-side with Worktree A** when its matching files land at
   `experiments/pr32-smoke-check/{slug}.md`.
4. **Decide on D1-D5** (the RECONSIDER list). The biggest are D2 (separate
   table) and D3 (PATTERN B chunk_id) — both affect ADR-0015 (synthesis) wording.
5. **If Worktree A's recall metrics show parity with B** — start the blog Angle A
   draft ("I built RAG twice") immediately; the comparison material is real.

## What was NOT completed (and why)

- **T10 — legacy PGVector port.** Explicitly skipped in finalize-mode per
  operator instruction. ~1-2h of solo work on a fresh session.
- **`jmi rag-lc-embed` / `jmi rag-lc-query` CLI commands.** Deferred to a
  follow-up PR per ADR-0015b §10 — the benchmark harness consumes `RagPipeline`
  directly, so a user-facing CLI isn't on the critical path until the operator
  decides whether to ship Worktree B as a user-visible alternative.
- **Live benchmark against Worktree C's harness.** Worktree C's harness is not
  in scope for this worktree — only the public `RagPipeline.retrieve_top_k` /
  `generate_bullets` surface that the harness will call.

## Confirmation: no push happened

```
git log --oneline origin/feat/phase3-pr3.2-B 2>&1 | head -1
→ fatal: ambiguous argument 'origin/feat/phase3-pr3.2-B' (or similar — no remote)
```

All work stays in worktree B; operator merges on review.
