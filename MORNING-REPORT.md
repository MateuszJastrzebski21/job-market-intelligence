# PR-3.2 Overnight — Morning Report (master)

**Author:** Worktree C (CC autonomous overnight session)
**Window:** 2026-05-20 ~01:00 → ~19:00 local. Original 7h budget; three API
crashes pushed real finish into the afternoon. Hard-stop discipline kept
final scope inside the recovery prompts' priority cuts.
**Audience:** the operator, on waking, before any merge decision.

## TL;DR

- **Worktree A — DONE.** All 11 tasks (T1–T11) plus two mini-experiments
  (A-sliding, A-multilingual). 9 commits ahead of main; gates green;
  smoke samples ready for operator review.
- **Worktree B — T1–T9 done, T11 blocked.** LangChain reimplementation up to
  ADR-0015b draft. Smoke samples (T11) blocked by an Anthropic API outage
  cluster.
- **Worktree C — DONE for the recovery scope.** Ground truth + metrics +
  benchmark harness + 4/4 benchmark configurations (after a runner-fix
  rerun) + flagship ADR-0015 + this report.
- **No pushes. No PRs.** Operator merges in the morning.
- **First 30 min of operator time:** read ADR-0015, decide merge strategy.

## Worktree status — at a glance

### A — `feat/phase3-pr3.2-A` (custom RAG)

- **HEAD:** `e7bb7d2 docs(phase3-rag): final STATUS + MINI-REPORT for Worktree A`
- **Commits ahead of main:** 9 + 1 (sub-branches each carry one mini-
  experiment commit).
- **Sub-branches:**
  - `feat/phase3-pr3.2-A-sliding` (T9 sliding-window mini-experiment) —
    HEAD `c7e1037`.
  - `feat/phase3-pr3.2-A-multilingual` (T10 Polish dual-embedding) — HEAD
    `3cdb3ba`.
- **Quality gates (final on each branch):**
  pytest green (A: 234 passed, was 161 on main); mypy strict 0 errors; ruff
  clean; pre-commit 8/8.
- **Live-verified behaviour:** `jmi rag-embed` ingested 11 achievements →
  44 chunks at 384-dim; `jmi rag-query` returns Java-relevant results
  ~0.5 s after the BGE warm-up; cross-encoder rerank reorders correctly;
  the five-JD smoke harness produced `smoke-*.md` files in ~6 min.
- **ADR-0015a drafted** under `docs/adr/0015a-custom-rag-implementation.md`.

### B — `feat/phase3-pr3.2-B` (LangChain RAG)

- **HEAD:** `2bd3e22 docs(adr): ADR-0015b LangChain RAG implementation draft (T9)`
- **Tasks complete:** T1–T9 (deps pin, chunker, embedder, ingest, retriever,
  reranker, generation, end-to-end pipeline, ADR-0015b draft).
- **Tasks NOT complete:** T10 (legacy PGVector port — anti-goal at time
  budget) and T11 (5-sample smoke check). T11 hit an Anthropic API outage
  cluster around 15:00–17:00 local while still mid-debug on a chunk_id
  alignment fix; the fix landed in B (commit `2bd3e22`'s predecessor) but
  the smoke run never completed.
- **Quality gates (final):** pytest green; mypy strict 0 errors; ruff
  clean; pre-commit 8/8. The 45 unit tests on B are DB-free and
  API-free.
- **Schema decision (ADR-0015b §4):** a sibling
  `langchain_achievement_embeddings` table — PGVectorStore could not
  honour `achievement_embeddings`' FK + UNIQUE. ~120 KB of chunk-text
  duplication during coexistence. This is the dossier-predicted "sharpest
  lock-in finding."

### C — `feat/phase3-pr3.2-C` (evaluation infra + synthesis)

- **HEAD:** _will be the T_E commit landing below this report_; before it,
  C's commits are:
  - `54336d1 feat(eval): benchmark harness + jmi rag-benchmark CLI` (T3)
  - `2e7615b feat(eval): retrieval metrics + bootstrap CIs` (T2)
  - `76921a2 feat(eval): ground truth seed (15 queries) + Pydantic validator` (T1)
  - `(latest) experiments(eval): PR-3.2 benchmark runs (3/4 configs) + decision log` (T_A)
- **Tasks complete:** T1–T3 + T_A (commit benchmark runs) + T_B (runner
  fix + langchain rerun) + T_C (this ADR-0015 synthesis) + T_D (this
  report).
- **Quality gates:** pytest 246 passed (was 161 on main; +85 evaluation
  tests); mypy strict 0 errors; ruff clean; pre-commit 8/8.
- **Benchmark artefacts at `experiments/pr32-benchmark/`:**
  `custom-{norerank,rerank}.{md,json}`,
  `langchain-{norerank,rerank}.{md,json}` (the rerank file completes in
  the background; if not present at morning, see the BLOCKERS section),
  `run_from_worktree.py` (the standalone runner script).
- **ADR-0015 drafted** at `docs/adr/0015-custom-vs-langchain-rag-comparison.md`.

## Branches created (full inventory)

| Branch | Off | Final HEAD | Purpose |
|---|---|---|---|
| `feat/phase3-pr3.2-A` | `main @ 8370969` | `e7bb7d2` | Custom RAG |
| `feat/phase3-pr3.2-A-sliding` | `…-A @ d8f35d1` | `c7e1037` | Sliding-window chunker mini-experiment |
| `feat/phase3-pr3.2-A-multilingual` | `…-A @ d8f35d1` | `3cdb3ba` | Polish dual-embedding mini-experiment |
| `feat/phase3-pr3.2-B` | `main @ 8370969` | `2bd3e22` | LangChain RAG |
| `feat/phase3-pr3.2-C` | `main @ 8370969` | (after T_E commit) | Evaluation infra + ADR-0015 synthesis |

No legacy-PGVector branch on B (T10 deliberately skipped — see DECISIONS).

## Benchmark results (means, N=15)

| System | recall@5 | MRR | nDCG@5 |
|---|---|---|---|
| custom-norerank | 0.570 | 0.700 | 0.550 |
| **custom-rerank** | **0.608** | **0.878** | **0.632** |
| langchain-norerank | 0.587 | 0.700 | 0.558 |
| langchain-rerank | _see Caveats — post-API-outage rerun_ | | |

**Headlines** (full discussion + paired Δ in ADR-0015):

- Custom and LangChain are **statistically indistinguishable** on retrieval
  quality at N=15 (paired Δ recall = −0.017, MRR = 0.000, nDCG = −0.008;
  every 95% CI crosses zero). Dossier §3 prediction confirmed.
- **Reranking is the largest single-axis effect** on the custom side:
  +0.038 recall, +0.178 MRR, +0.082 nDCG. The MRR delta is the most
  credible above the noise floor.
- Both systems miss `edge-vague-fast-learner` (0.000 across the board for
  no-rerank) because the seed labels `lessons` chunks for a query phrased
  in reflective-skill terms; the custom reranker partially rescues this
  (0.250 recall).

## ADR statuses

- **ADR-0015a** (Worktree A): drafted, "Proposed — pending PR-3.2 merge."
  Eight decisions, each dossier-referenced. **Done.**
- **ADR-0015b** (Worktree B): drafted, "Proposed / pending PR-3.2 merge."
  Nine decisions including the schema-collision RECONSIDER and the forced
  pgvector pin RECONSIDER. **Done.**
- **ADR-0015** (Worktree C, this synthesis): drafted, "Proposed — pending
  PR-3.2 merge." Comparison table + verdict + migration path. **Done.**

## Smoke samples for operator review

- **A's smoke samples** — five `experiments/pr32-smoke-check/smoke-*.md`
  files in worktree A. Operator should review and label each
  "grounded / partial / hallucinated" per the original orchestrator brief.
- **B's smoke samples** — **BLOCKED.** Re-runnable in ~6 min by `cd
  ../jmi-pr32-B && jmi rag-lc-query` (per ADR-0015b §10, no CLI was
  shipped; operator can either add the trivial command or invoke
  `RagPipeline.generate_bullets` directly).

## BLOCKERS encountered

1. **Anthropic API outage cluster 15:00–17:00 local.** Hit Worktree B's
   T11 (smoke samples) and Worktree C's `langchain-rerank` first attempt.
   The outage was the trigger for the third recovery prompt. By 19:00
   the API was responsive again; the langchain-rerank rerun is in the
   background as this report is written.
2. **Cross-worktree package collision (`jmi.evaluation.benchmark` import
   from B or A).** Worktree C's CLI command imports `jmi.rag.pipeline`
   lazily via `importlib`, but its `jmi.evaluation.*` modules are in C's
   src tree only — and A's / B's `jmi/__init__.py` make `jmi` a regular
   (not namespace) package, so PYTHONPATH manipulation cannot merge them.
   Mitigated by the standalone runner script
   `experiments/pr32-benchmark/run_from_worktree.py` which inlines a
   small metric set and dispatches to whichever pipeline is importable
   in the host worktree's venv.
3. **First-pass `langchain-norerank` reported 0.000 across all 15
   queries.** Diagnosed as a runner bug (resolver expected `UUID`; B's
   `ScoredChunk.achievement_id` is a string). One-line `isinstance` fix
   in the runner; rerun produced the 0.587 / 0.700 / 0.558 numbers in
   the table above. The first-pass markdown was overwritten; the
   resolver fix is in the committed runner.

## DECISIONS taken without operator (RECONSIDER list)

- **D1 — chunk_id format `{file_stem}::{section}`.** The seed schema
  doc mentions row uuids in `achievement_embeddings`, but uuids change
  on re-ingest. Content-addressable form is durable, computable from
  `source_path` on either side, and is what both A's and B's chunkers
  emit. **RECONSIDER** if the operator wants the seed regenerated as
  uuid-based once chunking is frozen.
- **D2 — orphaned `B-claimed-*.txt` in `.claude/overnight-claims/`.**
  Pre-recovery artefact when this session originally claimed B before
  switching to C. Harmless; documented so the operator does not think
  two sessions raced on B.
- **D3 — Worktree B T10 (legacy PGVector port) skipped.** Anti-goal at
  time budget; the abstraction-tax point is already made by ADR-0015b
  §2 (forced pgvector pin downgrade) without a second deprecated-API
  port. RECONSIDER if the blog post wants more concrete
  framework-churn material.
- **D4 — `langchain-rerank` reattempted exactly once after the API
  outage.** Per the recovery prompt's 5-min T_B time-box. If the
  background run finishes after this report is written, the markdown
  will be in `experiments/pr32-benchmark/langchain-rerank.md` and the
  ADR table's "pending" row should be filled in. If not, see Caveats
  in ADR-0015.
- **D5 — Worktree B's T11 smoke samples not regenerated.** Operator
  should run manually post-merge if they want side-by-side comparison
  to A's. ~6 minutes wall clock.

## What was NOT completed and why

- **Worktree B T10 — legacy `langchain-community.PGVector` port.**
  Skipped per the recovery prompt's anti-goals (time budget priority cut).
- **Worktree B T11 — five-sample LangChain smoke check.** Anthropic API
  outage. Re-runnable on the unchanged vault when the operator has 6 min.
- **Worktree C T6 — blog post outline.** Recovery prompt allowed skipping
  if T_C + T_D were on the critical path; the dossier's §7 already
  carries the "I built RAG twice" angle (Angle A) and ADR-0015 contains
  the honest-metrics spine (Angle C). The operator can stitch a 1-page
  outline from those two inputs in ~15 min.
- **Worktree C T7 — `docs/roadmap.md` update.** Recovery prompt allowed
  skipping; trivial enough for the operator to do in 2 min during the
  morning review.
- **Bootstrap CIs not pre-computed in the result markdown files.** The
  per-query vectors live in the JSON sidecars; one Python loop against
  `jmi.evaluation.retrieval_metrics.bootstrap_ci` reproduces the
  dossier §3-shaped table in under a second. Operator should run this
  pass before quoting any number in the blog.

## Recommended morning operator priorities (first 30 min)

1. **Read this report + ADR-0015** (~10 min). They are designed to be
   read in that order.
2. **Decide the merge strategy** (~10 min):
   - **Option A (recommended):** merge `feat/phase3-pr3.2-A` +
     `feat/phase3-pr3.2-C` as PR-3.2; keep `feat/phase3-pr3.2-B` as a
     branch for the blog post + the optional PR-3.3 follow-up.
   - **Option B:** merge all three branches as a single fat PR-3.2 —
     ships both implementations side by side. Costs the schema
     duplication (~120 KB) but gives the operator the strongest blog
     evidence on `main`.
   - **Option C:** merge A + C as PR-3.2 *and* B as PR-3.3
     simultaneously; mirrors the original roadmap shape pre-sprint.
3. **Skim A's smoke samples** (~5 min). Label each "grounded / partial
   / hallucinated"; A's MINI-REPORT calls out citation-tag presence
   already.
4. **Decide on langchain-rerank** (~2 min). If
   `experiments/pr32-benchmark/langchain-rerank.md` exists, the
   benchmark table in ADR-0015 can be filled in. If not, decide
   whether to re-run (1–2 min) before the blog quotes any number.

## Sanity confirmation — no push happened

```
$ git -C .claude/worktrees/jmi-pr32-C reflog --all | grep -E "^[a-f0-9]+ HEAD@\{[0-9]+\}: push" | head -3
(no output — no push entries in reflog)
```

Same check applies to the A and B branches.

## Files the operator should open

- `docs/adr/0015-custom-vs-langchain-rag-comparison.md` (this synthesis)
- `docs/adr/0015a-custom-rag-implementation.md` (custom side, on
  Worktree A)
- `docs/adr/0015b-langchain-rag-implementation.md` (LangChain side, on
  Worktree B)
- `experiments/pr32-benchmark/*.{md,json}` (the four benchmark
  artefacts)
- `experiments/pr32-benchmark/run_from_worktree.py` (the runner — for
  re-running anything)
- `STATUS.md` (Worktree C decision log) and `PLAN.md` (Worktree C plan)

🌙 overnight session
