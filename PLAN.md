# PR-3.2 Worktree C — Plan

**Role:** evaluation infrastructure + flagship synthesis ADR + blog outline.
**Branch:** `feat/phase3-pr3.2-C` (off main @ 8370969).
**Sibling worktrees:** A (custom RAG, `feat/phase3-pr3.2-A`), B (LangChain,
`feat/phase3-pr3.2-B`). Both exist; A had no commits at recovery, B had at least
one commit (27bdde5).

## Sequencing

T1–T4 are infrastructure-only and **do not depend on A or B**. Build them now.

T5 (run benchmarks) blocks on A and B having runnable pipelines. Poll their
STATUS.md every ~20 min after T4 finishes. If neither is ready by ~04:00 (or my
proxy of "≥4h elapsed since C start"), log a BLOCKER and proceed to T6 with
whatever exists.

T6–T9 are write-up tasks that can run with partial benchmark results. The
flagship ADR-0015 and blog outline are the highest-value deliverables for the
operator's review window, so they must be drafted regardless of T5 outcome.

## Task plan

### T1 — Ground truth seed (`docs/ground_truth/rag_retrieval_seed.json`)

- Implement the Pydantic validator described in
  `docs/ground_truth/rag_retrieval_seed_schema.md`. Validator lives in
  `src/jmi/evaluation/retrieval_seed.py` (new), JSON file in
  `docs/ground_truth/rag_retrieval_seed.json`.
- 15 queries:
  - 5 single-achievement-focused (one per achievement archetype the operator
    has — Java backend, quant/options, agentic systems, ML competition,
    full-stack).
  - 5 cross-cutting (multiple matching achievements per query).
  - 3 Polish (for A's multilingual experiment).
  - 2 edge cases (vague phrasing, ambiguous intent).
- Each entry: `id`, `query`, `query_language` (`en`|`pl`), `relevant_chunk_ids`
  (1–5 ids), `notes`.
- **Open question to resolve:** the schema doc says chunk ids "refer to a row in
  the `achievement_embeddings` table" — but the table is empty at C's start
  (PR-3.1 created the schema but never populated it; PR-3.2 worktree A's T3 is
  what populates it). I cannot bind to live chunk row uuids that do not yet
  exist. **Decision (RECONSIDER):** use a synthetic, content-addressable chunk
  id of the shape `{achievement_slug}::{section}` (e.g.
  `java-backend-pricing::impact`) and treat that as the durable identifier.
  Both A and B can map their stored chunks to the same id at evaluation time
  via `(achievement_slug, section)`. This decouples the seed file from row
  uuid churn (which is desirable anyway — uuids would change on re-ingest).
  Documented in STATUS.md.
- Tests: schema validation; round-trip; required-field checks; unknown-field
  rejection.

### T2 — Retrieval metrics (`src/jmi/evaluation/retrieval_metrics.py`)

Replace `raise NotImplementedError` stubs with real implementations:

- `recall_at_k(ranked_ids, relevant_ids, k) -> float` — fraction in top-k; 1.0
  on empty `relevant_ids`.
- `mrr(ranked_ids, relevant_ids) -> float` — first-relevant reciprocal rank.
- `ndcg(ranked_ids, relevance, k) -> float` — keep existing graded signature;
  binary callers pass `{id: 1.0 for id in relevant}`.
- Plus: `bootstrap_ci(per_query_scores, confidence=0.95, n_resamples=1000) ->
  (lo, hi)` — percentile CI per dossier §3.
- Plus: `paired_bootstrap_ci(scores_a, scores_b, confidence=0.95,
  n_resamples=1000) -> (mean_delta, lo, hi)` — same resampled indices, so
  per-query difficulty cancels (dossier §3).
- Tests for each: happy path, edge cases (empty, all-irrelevant, all-relevant,
  k larger than result).

### T3 — Benchmark harness (`src/jmi/evaluation/benchmark.py`)

- `BenchmarkResult` pydantic model: per-query metric rows + aggregate metric
  rows with CIs + run metadata (pipeline name, config dict, seed version,
  timestamp).
- `Pipeline` Protocol — exposes `retrieve(query: str, k: int) -> list[str]`
  returning chunk ids. Both A's and B's pipeline classes satisfy this once they
  expose `retrieve_top_k`.
- `benchmark_pipeline(pipeline, ground_truth, k=5) -> BenchmarkResult` — runs
  each query, computes recall@k, MRR, nDCG@k, returns the result.
- CLI: `jmi rag-benchmark --pipeline {custom|langchain} [--rerank/--no-rerank]
  [--k INT] [--seed PATH] [--out PATH]`. CLI command lives in `src/jmi/cli.py`.
- Tests: synthetic ground truth + a stub pipeline; metric values match hand
  calculations.

### T4 — Benchmark result formatter

- `format_benchmark_markdown(result: BenchmarkResult) -> str` — renders the
  per-pipeline table + per-query breakdown.
- `format_comparison_markdown(results: list[BenchmarkResult]) -> str` — the
  side-by-side table from dossier §3 with paired Δ row and CIs.
- CLI flag `--out PATH` writes the rendered markdown to disk under
  `experiments/pr32-benchmark/`.
- Tests: render against a fixed result; snapshot text.

### T5 — Run benchmarks (WAIT FOR A AND B)

Poll `.claude/worktrees/jmi-pr32-{A,B}/STATUS.md` every ~20 min. Trigger
condition: their STATUS.md says T8 (end-to-end pipeline) is done with passing
tests.

Configurations to run:
- `custom-per-section` ± rerank
- `langchain-per-section` ± rerank
- `custom-sliding-window` ± rerank (if A's T9 done)
- `custom-multilingual` (Polish queries only, if A's T10 done)

Save each to `experiments/pr32-benchmark/{config}.md`. Save the comparison
table to `experiments/pr32-benchmark/comparison.md`.

If A and B not ready by 4h elapsed: log BLOCKER in STATUS.md, run on whatever
exists (possibly only one side), and call it out in the morning report.

### T6 — ADR-0015 synthesis
`docs/adr/0015-custom-vs-langchain-rag-comparison.md`. Status: Proposed.
Sections per orchestrator brief — comparison table, where each wins,
verdict + reasoning, migration path.

### T7 — Blog post outline
`docs/blog/pr-3.2-i-built-rag-twice.md`. Angle A spine from dossier §7,
honest-metrics framing from Angle C.

### T8 — Roadmap update
`docs/roadmap.md` — collapse PR-3.2/PR-3.3 split into the actual dual-builder
shape, single commit, no other changes.

### T9 — MORNING-REPORT.md at workspace root
At 06:30 local. Sections per orchestrator brief. As worktree C I own the
master report — A and B write their own MINI-REPORT.md.

## Quality gates

Every commit:
```
uv run pytest -q
uv run mypy src/
uv run ruff check src/ tests/
uv run pre-commit run --all-files
```
Baseline: 161 tests at commit 8370969.

## Conventions

- Conventional commits.
- Sign-off trailer: `🌙 overnight session`. **No** `Co-Authored-By` (per user
  memory `feedback_commit_pr_attribution`).
- One commit per task ideally. WIP commits if needed, squash before logging
  in file-by-file commit log.

## Out of scope for C

- Custom RAG implementation (worktree A owns).
- LangChain implementation (worktree B owns).
- Generation pipeline (A/B each own their generator).
- Mini-experiments (sliding window, multilingual) — A/B own.
