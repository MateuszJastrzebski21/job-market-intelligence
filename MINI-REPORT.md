# Worktree A — Mini Report (PR-3.2 Custom RAG)

**Branch:** `feat/phase3-pr3.2-A` (with sub-branches `…-sliding`, `…-multilingual`)
**Window:** 2026-05-20 14:03 → 17:05 local (3h 02m of net work after the
14:03 recovery; original 01:00–07:00 budget was eaten by an API-timeout
pre-T1 and a clean restart).
**Operator notes:** auto mode, write-with-trace, no pushes, no PRs.

## TL;DR

All 11 tasks delivered:

- T1–T8 core implementation **shipped on `feat/phase3-pr3.2-A`** with
  every commit passing pytest + mypy strict + ruff + pre-commit.
- T11 smoke-check harness shipped on the same branch; the five
  `smoke-*.md` artifacts are produced locally (gitignored — H1/S-2).
- T9 sliding-window mini-experiment shipped on
  `feat/phase3-pr3.2-A-sliding`. Dossier §1.c prediction confirmed
  qualitatively.
- T10 Polish dual-embedding mini-experiment shipped on
  `feat/phase3-pr3.2-A-multilingual` as the *single-store* partial.
  The full dual-store + Alembic migration was time-boxed out and is a
  named follow-up.

## Branches created

| Branch | Off | Commits added | Final HEAD |
|---|---|---|---|
| `feat/phase3-pr3.2-A` | `main @ 8370969` | 9 | `d8f35d1` |
| `feat/phase3-pr3.2-A-sliding` | `…-A @ d8f35d1` | 1 | `c7e1037` |
| `feat/phase3-pr3.2-A-multilingual` | `…-A @ d8f35d1` | 1 | `3cdb3ba` |

No pushes; no PRs; no remote interaction (`reflog --all | grep -i "push"`
returns only old `origin/main` updates that predate this session).

## Commits per branch

### `feat/phase3-pr3.2-A` (9 commits ahead of main)

```
d8f35d1 feat(phase3-rag): T11 — smoke-check harness for 5 sample JDs
7cb53f7 docs(adr): ADR-0015a draft — custom RAG implementation (PR-3.2 worktree A)
abd563e feat(phase3-rag): T7 — Anthropic Claude bullet generator
0d81aa2 feat(phase3-rag): T6 — RagPipeline + `jmi rag-query` CLI
443d207 feat(phase3-rag): T5 — bge-reranker-base cross-encoder (drop-in)
944737b feat(phase3-rag): T4 — pgvector cosine retriever (CustomRetriever)
c679a56 feat(phase3-rag): T3 — ingest pipeline + `jmi rag-embed` CLI
de8cab0 feat(phase3-rag): T2 — BGE-small-en-v1.5 embedder wrapper
1018e10 feat(phase3-rag): T1 — per-section chunker with [Title — Section] header
```

### `feat/phase3-pr3.2-A-sliding` (1 commit ahead of A)

```
c7e1037 exp(phase3-rag): T9 — sliding-window chunker mini-experiment
```

### `feat/phase3-pr3.2-A-multilingual` (1 commit ahead of A)

```
3cdb3ba exp(phase3-rag): T10 — Polish-routing multilingual mini-experiment
```

## Quality gates — final on each branch

All three branches:

- `uv run pytest -q` — green
- `uv run mypy src/` — 0 errors
- `uv run ruff check src/ tests/` — clean
- `uv run pre-commit run` — 8/8 on every changed file

Test count on **A**: 234 passed (was 161 on main; +73 RAG-package tests).
Test count on **A-sliding**: +6 sliding-chunker tests.
Test count on **A-multilingual**: +6 language-routing tests.

## Live-verified behaviour (end-to-end)

| Verification | Result |
|---|---|
| `jmi rag-embed` against vault | 11 achievements → 44 chunks at 384-dim |
| `jmi rag-query --no-rerank` (Java query) | top-3 are Java-relevant achievements, ~0.5 s after BGE warm |
| Live cross-encoder rerank | reorders Java query — bumps Junior Java Developer to #1 |
| Five-JD smoke harness | 5 `smoke-*.md` files produced, ~6 min total, ~2k input / ~500 output tokens per JD; bullets carry `(chunks: N, M)` citations as the system prompt enforces |
| Sliding-window re-ingest | 34 chunks, JMI flagship crowds top-K with three near-duplicate windows |
| Multilingual re-ingest | 44 chunks, Polish probes land on the same achievements as their English equivalents |

## ADR-0015a status

- **Drafted** (`docs/adr/0015a-custom-rag-implementation.md`).
- Status header: `Proposed — pending PR-3.2 merge.`
- 8 decisions (D-1 through D-9 minus a renumber) each cross-referenced
  to the dossier.
- Mini-experiments cited; cross-refers ADR-0015b (Worktree B) and the
  synthesis ADR-0015 (Worktree C).
- **Gaps:** none — every dossier-driven choice has a recorded decision.
  The mini-experiment FINDINGS files (T9, T10) are referenced but live
  on the sub-branches, not on A — the synthesis ADR will be the bridge.

## Blog post outline status

Not done in Worktree A — the blog post is Worktree C's deliverable
(per the orchestrator brief §C/T7). A pulled the framing from dossier
§7 into ADR-0015a's references but did not draft the post itself.

## Smoke-check outputs ready for operator review

Local files at
`experiments/pr32-smoke-check/custom/smoke-*.md` (5 files,
gitignored). Format pinned by the harness:

- Input JD (verbatim)
- Top-5 retrieved chunks with chunk_id + achievement_id + scores +
  full chunk text
- Generated bullets with `(chunks: N, M)` citations
- Notes section with "grounded / partial / hallucinated" labels for
  the operator to fill in

Reproduce: `set -a; source .env; set +a; uv run python
experiments/pr32-smoke-check/custom/run.py`.

## Mini-experiment outputs ready for operator review

- `experiments/pr32-sliding/COMPARE.md` + `FINDINGS.md` on the
  `…-A-sliding` branch.
- `experiments/pr32-multilingual/COMPARE.md` + `FINDINGS.md` on the
  `…-A-multilingual` branch.

Both have a "Reproduce" section. The DB was restored to BGE
per-section state at the end of each experiment (re-ran `jmi
rag-embed` on switch back to A), so the operator can spot-check the
A-branch behaviour against either FINDINGS.md.

## BLOCKERS

_None unresolved._ Two minor friction points handled in-session:

- The shell's `ANTHROPIC_API_KEY=""` shadows the `.env` value during
  Claude Code sessions. Worked around with `set -a; source .env; set +a`
  before the harness invocations. **Recommendation:** the operator may
  want to add a small helper script or document this in the README
  if other agents need to call Anthropic from the codebase.
- `sentence_transformers.CrossEncoder.predict` types `inputs` as a
  multimodal union that mypy strict cannot satisfy from a typed
  `list[list[str]]`. Resolved with a single `cast(Any, pairs)` and a
  comment — the only `cast`-style narrowing in the RAG package, no
  `type: ignore` used anywhere.

## DECISIONS taken without operator

Each labelled **RECONSIDER** is a judgment call worth a second look.

- **D-A1 (RECONSIDER).** Added a defensive Python-side `[:k]` slice
  to `CustomRetriever.retrieve` on top of the SQL `LIMIT :k`. Makes
  stub-session unit tests trivial; belt-and-suspenders. Reconsider
  if a future diagnostics path wants extra rows.
- **D-A2 (RECONSIDER).** Single-chunk reranker input is *not* a
  pass-through — the cross-encoder still runs so the returned `score`
  field is uniformly the CE logit. The alternative (skip for n=1)
  surprises callers that pin score semantics.
- **D-A3.** BGE query-instruction prefix
  (`"Represent this sentence for searching..."`) left as a *commented*
  seam in `embedding.py`. Flipping it on is a future single-line
  change behind a benchmark result. Not a hidden default.
- **D-A4.** `CustomEmbedder` rejects any model name other than the
  pinned BGE constant. The multilingual experiment introduced a
  separate class rather than parameterise the existing one.
- **D-A5 (RECONSIDER).** T10 single-store partial. The full
  dual-store routing (per-chunk `embedding_model_name` Alembic
  column + two embeddings per chunk) was time-boxed out. The
  `RoutingEmbedder` class is the seam the follow-up plugs into.
  Reconsider whether to land the migration as part of PR-3.3 or as
  its own PR.

## What was NOT completed and why

- **T10 dual-store full design** — Alembic migration adding
  `embedding_model_name` to `achievement_embeddings` plus the
  two-rows-per-chunk write path. Cut to single-store fallback to
  keep T9 + T10 + smoke-check + MINI-REPORT inside the post-recovery
  time budget. Documented in commit message + `FINDINGS.md`.
- **STATUS.md mid-session update at 30-min cadence.** Updated twice
  total (PLAN + halfway). Could have been more frequent but the
  commit messages serve the audit-trail purpose with similar fidelity.
- **No `git push`** — confirmed. No `gh pr create` either. Pure
  local artefact per the orchestrator's write-with-trace rule.

## Suggested operator priorities for first 30 min of morning

1. **Read smoke files** (5 files at
   `experiments/pr32-smoke-check/custom/smoke-*.md`). Label each
   bullet grounded/partial/hallucinated — those labels feed the
   ADR-0015 synthesis row that Worktree C owns.
2. **Skim ADR-0015a** to confirm the 8 decisions match operator
   intent. Look hardest at D-A3 (no bge query prefix) and D-A5
   (T10 single-store partial) — both are reversible cheaply.
3. **Pick the synthesis path.** Worktree C's brief assumed C waits
   on A+B. With A done and B in unknown state, the operator may want
   to (a) wait for B before C starts, or (b) decide that A's
   commit-message + ADR-0015a output is enough to write a partial
   ADR-0015 from A alone. Either path is viable.

## Confirmation: no PR was opened

`git reflog --all | grep -i "push"` returns only old `origin/main`
update entries from before this session. No `feat/phase3-pr3.2-A`,
`-sliding`, or `-multilingual` branch was ever pushed.
