# Worktree A — STATUS (final)

**Branch:** `feat/phase3-pr3.2-A`
**Sub-branches:** `…-sliding`, `…-multilingual`
**Started (recovery):** 2026-05-20 14:03 local
**Final update:** 17:05 local
**See:** `MINI-REPORT.md` for the operator-review summary.

## Tasks — all completed

| Task | Branch | Commit |
|---|---|---|
| T1 — per-section chunker | A | `1018e10` |
| T2 — BGE-small-en-v1.5 embedder | A | `de8cab0` |
| T3 — ingest pipeline + `jmi rag-embed` CLI | A | `c679a56` |
| T4 — pgvector cosine retriever | A | `944737b` |
| T5 — bge-reranker-base cross-encoder | A | `443d207` |
| T6 — RagPipeline + `jmi rag-query` CLI | A | `0d81aa2` |
| T7 — Anthropic Claude bullet generator | A | `abd563e` |
| T8 — ADR-0015a draft | A | `7cb53f7` |
| T11 — five-JD smoke-check harness | A | `d8f35d1` |
| T9 — sliding-window mini-experiment | A-sliding | `c7e1037` |
| T10 — Polish-routing mini-experiment | A-multilingual | `3cdb3ba` |

## BLOCKERS

None unresolved. Two friction points (shell-env shadowing of
ANTHROPIC_API_KEY; lossy sentence-transformers stubs on CrossEncoder)
documented in MINI-REPORT.md.

## DECISIONS taken without operator

See MINI-REPORT.md §"DECISIONS taken without operator" for the full
list of five, with three labelled **RECONSIDER**.

## Quality gates — final on each branch

- `uv run pytest -q` — A: 234 passed; A-sliding: 240 passed; A-multilingual: 240 passed
- `uv run mypy src/` — 0 errors on every branch
- `uv run ruff check src/ tests/` — clean on every branch
- `uv run pre-commit run` — 8/8 on every changed file

## Baseline restored

The dev DB is back to **44 BGE-per-section chunks** as of 17:05 local
(`uv run jmi rag-embed` re-run after the T10 sub-branch experiment).
Operator can switch to any sub-branch and re-run that sub-branch's
`run.py` to reproduce its findings; switching back to A and running
`jmi rag-embed` restores the canonical state.

## No remote interaction

Confirmed no `git push`, no `gh pr create`. All artefacts local.
