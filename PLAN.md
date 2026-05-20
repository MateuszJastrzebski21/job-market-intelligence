# Worktree A — Custom RAG: Implementation Plan

**Branch:** `feat/phase3-pr3.2-A` off `main` @ `8370969`
**Started (recovery):** 2026-05-20 14:03 local
**Operator brief:** overnight orchestrator, recovery mode after pre-T1 timeout.

## Scope (from orchestrator §[WORKTREE A])

Build a custom RAG retrieval pipeline against the existing
`achievement_embeddings` table:

- Per-section chunking with prepended `[Title — Section]` header
- BGE-small-en-v1.5 embeddings (384-dim, drop-in for current `Vector(384)` column)
- pgvector cosine retrieval, top-K=5
- bge-reranker-base as drop-in optional stage
- Claude (opus 4.7) generation step grounded in retrieved chunks
- ADR-0015a draft documenting decisions

## Fixed decisions (from operator)

- Chunking: per-section, header = `[{title} — {section}]`
- Embedding: `BAAI/bge-small-en-v1.5` via sentence-transformers; 384-dim → same `Vector(384)` column
- Reranker: `BAAI/bge-reranker-base`, default ON for benchmark, disable-able via flag
- Top-K: 5
- Generator: `claude-opus-4-7` (default), Anthropic SDK directly (no LangChain — Worktree B owns the LC build)

## Task breakdown — priority order

Core (must deliver):
- **T1** — `src/jmi/rag/chunking.py` + tests
- **T2** — `src/jmi/rag/embedding.py` + tests (lazy load, monkeypatchable)
- **T3** — `src/jmi/rag/ingest.py` + CLI `jmi rag-embed` + tests
- **T4** — `src/jmi/rag/retrieval.py` + tests
- **T5** — `src/jmi/rag/reranking.py` + tests (lazy load, monkeypatchable)
- **T6** — `src/jmi/rag/pipeline.py` + CLI `jmi rag-query` + tests
- **T7** — `src/jmi/rag/generation.py` + tests (prompt validation only; live API exercised in T11)
- **T8** — `docs/adr/0015a-custom-rag-implementation.md`

Stretch (deliver if time):
- **T11** — `experiments/pr32-smoke-check/custom/*.md` (5 JDs)
- **T9** — sliding-window mini-experiment on sub-branch `feat/phase3-pr3.2-A-sliding`
- **T10** — Polish dual-embedding on sub-branch `feat/phase3-pr3.2-A-multilingual`

Cut order if pressed: T10 → T9 → T11. Core T1–T8 protected.

## Architecture notes

- `analytics/embed.py` keeps MiniLM as the Phase 2 dependency. RAG embeddings get
  their own module (`rag/embedding.py`) to avoid coupling Phase 2 clustering to
  the BGE upgrade. The model name is module-level constant so it's easy to swap
  in T10.
- The chunking layer is pure — input is a Pydantic `Achievement`, output is a
  list of Pydantic `Chunk` models. No DB, no embedding model — trivially unit-testable.
- The retriever opens its own session via `get_session()`-style injection, but
  unit tests inject a fake session that returns canned rows. No live embeddings
  in unit tests (mirrors the H5/E-3 constraint).
- The reranker is a `Protocol` — `CustomReranker` is the default cross-encoder
  implementation, but the pipeline accepts any `Reranker | None`, so swapping or
  disabling is trivial.
- Logging follows H7/O-4 — events named `rag.chunk.done`, `rag.embed.done`,
  `rag.retrieve.done`, `rag.rerank.done`, `rag.generate.done`. Per H1/S-2:
  **no chunk body in logs**, only ids/lengths/counts.

## Commit granularity

One commit per task. Tests included in the same commit as the production code.
Conventional commits, `feat(phase3-rag): T# — …` style. Trailer:
`🌙 overnight session`.

## Quality gates (every commit)

- `uv run pytest -q` — 161 baseline holds
- `uv run mypy src/` — 0 errors
- `uv run ruff check src/ tests/` — clean
- `uv run pre-commit run --all-files` — 8/8

## STATUS.md cadence

Updated every ~30 min and after each task commit.

## End-of-session

Write `MINI-REPORT.md` summarising commits per task, quality gates, blockers,
decisions taken without operator, and what was deferred.
