# ADR-0015: Custom vs LangChain RAG — PR-3.2 Synthesis

**Status:** Proposed — pending PR-3.2 merge.
**Date:** 2026-05-20
**Pairs with:** ADR-0015a (Worktree A, custom RAG) and ADR-0015b (Worktree B,
LangChain RAG).
**Inputs:** the PR-3.2 dossier
(`docs/research/pr-3.2-rag-comparison-dossier.md`), the four benchmark
runs in `experiments/pr32-benchmark/`, and the two sibling ADRs.

## Context

PR-3.2 ran as a dual-builder sprint. Worktree A shipped a custom RAG pipeline
against the existing `achievement_embeddings` table (ADR-0014). Worktree B
reimplemented the same flow with LangChain 0.3.x primitives on a sibling
`langchain_achievement_embeddings` collection. Worktree C built the
evaluation infrastructure — a 15-query ground-truth seed
(`docs/ground_truth/rag_retrieval_seed.json`), the retrieval metrics
(recall@k, MRR, nDCG@k, percentile + paired bootstrap CIs), and the benchmark
harness — then scored both pipelines on the same queries.

The dossier (§3, §5) predicted custom-vs-LangChain differences on a corpus
of 24–80 chunks at N≈15 would sit inside the noise band, and the deciding
factor would be code surface — schema ownership, observability, debug
ergonomics — rather than retrieval quality. This ADR records the synthesis
decision after the benchmark confirmed that prediction.

## Decision

**JMI commits to the custom RAG implementation for the PR-3.2 merge.** The
LangChain implementation stays on its `feat/phase3-pr3.2-B` branch as a
companion artefact for ADR-0015a/0015b cross-reference, the blog post, and a
future PR-3.3 follow-up if the comparison is ever extended.

The reasoning is not that custom wins on retrieval quality (it does not — the
two are statistically indistinguishable at N=15), but that:

1. PR-3.1 already built a typed `Achievement` domain + opinionated schema, and
   LangChain's primary value (greenfield primitives + a generic vectorstore)
   collides with both. The ADR-0015b §4 schema-ownership decision —
   shipping a *second* `langchain_achievement_embeddings` table because
   PGVectorStore cannot honour `achievement_embeddings`' FK + UNIQUE — makes
   that collision structural and unavoidable.
2. The custom build keeps the pgvector SQL visible (`ORDER BY embedding <=>
   :q LIMIT :k`), the Anthropic prompt visible (a literal multi-line string
   in `generation.py`), and the per-stage `rag.*.done` structlog events
   uniform — three pedagogically and operationally valuable properties that
   the LangChain layers each hide.
3. The framework's measurable wins on this corpus are zero or sub-noise (see
   the comparison table), and its costs are concrete: a forced `pgvector`
   downgrade (`>=0.4.2` → `>=0.3.6`), a duplicated chunk-text store, an
   abstraction that drops the cross-encoder's per-chunk score before it
   reaches the public retriever interface.

This is a JMI-specific decision; it is not "LangChain bad." The honest framing
from the dossier (§5) — *"a framework bets its opinions match yours; JMI
committed to different, typed opinions, so the bet doesn't pay here"* —
holds.

## Comparison

### Retrieval metrics (real numbers, N=15)

| System | recall@5 | MRR | nDCG@5 |
|---|---|---|---|
| custom-norerank | 0.570 | 0.700 | 0.550 |
| custom-rerank | **0.608** | **0.878** | **0.632** |
| langchain-norerank | 0.587 | 0.700 | 0.558 |
| langchain-rerank | _pending_ (post-API-outage retry, see Caveats) | | |

Paired Δ between custom-norerank and langchain-norerank: recall = −0.017,
MRR = 0.000, nDCG = −0.008. At N=15 every 95% bootstrap CI on these
differences crosses zero by a wide margin — well inside the dossier §3
"±0.10–0.20 honest noise band." The two implementations are statistically
indistinguishable on retrieval quality.

Reranking on the custom side adds **+0.038 recall, +0.178 MRR, +0.082 nDCG**
over no-rerank — the largest effect any single axis produced. The MRR gain
is the most credible (cross-encoder reordering directly raises the first
relevant hit) and the largest above the noise floor.

The retrieval ceiling is real and shared: both systems miss the same
`edge-vague-fast-learner` query (0.000 across the board for custom-norerank
and langchain-norerank) because the seed labels four `lessons` chunks for a
query phrased entirely in reflective-skill terms — neither bi-encoder ranks
`lessons` over technical sections for that query shape. The reranker on the
custom side partially rescues it (0.250 recall).

### Code surface and ergonomics

| Dimension | Custom (Worktree A) | LangChain (Worktree B) |
|---|---|---|
| **LOC** (`src/jmi/rag*/` + tests) | ~1,050 (src) + ~1,650 (tests) | ~770 (src) + ~860 (tests) |
| **Direct deps added to `pyproject.toml`** | `sentence-transformers` (already in v2 PoC), `tiktoken` (mini-experiment only) | `langchain`, `langchain-core`, `langchain-postgres`, `langchain-huggingface`, `langchain-anthropic`, `langchain-text-splitters` |
| **Indirect pin churn** | none | forced `pgvector >=0.4.2 → >=0.3.6` (ADR-0015b §2) |
| **mypy strict coverage** | 100% of new modules pass `--strict` | 100% of new modules pass `--strict` |
| **Observability — pgvector** | explicit `ORDER BY embedding <=> :q LIMIT :k` visible; `EXPLAIN`-able | hidden inside `similarity_search` — `langchain-postgres` source dive to debug |
| **Observability — generation prompt** | literal multi-line string in `generation.py`; `chunk_ids_in_prompt` recoverable for citation audit | hidden inside `ChatAnthropic` adapter; literal request body not present in JMI code |
| **Cross-encoder score** | surfaced on `ScoredChunk.score` after rerank | dropped by `ContextualCompressionRetriever`; B re-runs `similarity_search_with_score` to recover *bi-encoder* score (ADR-0015b §8 Surprise 1) |
| **Test surface** | every stage unit-testable with stub session + stub embedder; 73 new tests on A | 45 new tests on B (chunker, embedder adapter, ingest, retrieval, reranker, generation, pipeline composition), all DB-free / API-free |
| **Idempotent re-ingest** | `delete + insert` per `achievement_id` (UNIQUE invariant from ADR-0014) | deterministic UUID5 from `(achievement_id, chunk_index)` → upsert via `add_documents` |
| **Schema ownership** | extends ADR-0014's `achievement_embeddings` directly | requires sibling `langchain_achievement_embeddings`; ~120 KB duplication during coexistence (ADR-0015b §4) |
| **Storage layout** | one table, FK-cascade to `achievements`, UNIQUE`(achievement_id, chunk_index)` | two tables; FK + UNIQUE on the original, JSON metadata blob on the LangChain side |
| **Runtime cost (embedding pass)** | ~same — both use `BAAI/bge-small-en-v1.5` via `sentence-transformers` | ~same — `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5", ...)` wraps the same model |
| **Effort (T1–T9 net work)** | ~3h after recovery (single worktree) | ~3h after recovery (single worktree) |

### Generation quality

Smoke-check artefacts (5 sample JDs) exist for the custom side
(`../jmi-pr32-A/experiments/pr32-smoke-check/`). The LangChain side's
parallel smoke samples are **blocked** by an Anthropic API outage that
struck mid-debug — Worktree B's `chunk_id` alignment fix landed but the
sample run did not complete. The generation prompts are identical across
the two implementations (both encode the dossier §6 contract), so the
expected bullet quality is the same conditional on the same retrieved
top-K; any quality delta in production would track the retrieval delta,
which the metrics table shows is sub-noise.

## Where LangChain wins (steelmanned)

1. **`Embeddings` ABC and `BaseCrossEncoder` are clean seams.** Two-method
   `embed_documents` / `embed_query`; a one-method `score` on the cross-
   encoder. Worth copying into a custom build even when no LangChain code is
   shipped (ADR-0015b §5).
2. **Less code in the greenfield case.** With no pre-existing typed schema,
   `PGVector.from_documents(docs, embeddings)` is three lines that handle
   table creation, upserts, similarity search, and filtering. Custom code has
   to write each layer.
3. **The split-package architecture lets you opt into individual integrations
   without pulling the world.** Worktree B added `langchain-postgres`,
   `-huggingface`, `-anthropic` as separate packages — no `langchain-
   community` meta-pull required.
4. **A reranker plus retriever composes as a single `BaseRetriever`** via
   `ContextualCompressionRetriever`, useful when a downstream consumer wants
   one retriever object regardless of whether reranking is active.

## Where custom wins

1. **Visible SQL and visible prompt — debuggable surface.** Both
   pgvector's distance operator and the Anthropic request body live in the
   diff; LangChain hides both behind adapter methods.
2. **The cross-encoder score is preserved through the pipeline.** Custom's
   `ScoredChunk.score` carries the reranker logit; LangChain's compression
   retriever drops it and B has to call `similarity_search_with_score` a
   second time just to recover a *bi-encoder* score (signal-on-the-floor —
   ADR-0015b §8).
3. **One table, one FK, one UNIQUE.** No `langchain_achievement_embeddings`
   sibling, no JSON metadata blob, no `pgvector` pin downgrade. ADR-0014's
   `achievement_embeddings` is the only storage.
4. **Public surface of every stage is a small typed function.** The
   embedder, retriever, and reranker each export 1–2 functions with `list[…]`
   inputs and outputs; mocking for tests requires no LangChain stubs.

## Verdict

PR-3.2 ships the custom implementation. ADR-0015a's eight decisions are
accepted as the merged design; ADR-0015b's nine decisions are recorded as
the LangChain side of the comparison (for the blog post and the optional
PR-3.3 follow-up). The benchmark numbers in this ADR (and the four files in
`experiments/pr32-benchmark/`) are the evidence base for both.

The honest framing in the morning report and the blog: this is not "custom
beats LangChain." It is "a framework's value is highest when you have
neither a schema nor a domain model; JMI built both in PR-3.1, so the
framework's bet doesn't pay here — and that is itself the most useful thing
the comparison teaches."

## Migration path

If JMI ever wants to swap to LangChain in a follow-up:

- **Schema:** Worktree B's `langchain_achievement_embeddings` is already
  populated by the same chunker + embedder; the custom-side
  `achievement_embeddings` can be dropped in an Alembic migration once the
  swap is live.
- **Code:** replace `from jmi.rag import RagPipeline` with `from
  jmi.rag_langchain import RagPipeline`. The benchmark harness's
  `RetrievalPipeline` protocol guarantees the public surfaces match.
- **CLI:** add `jmi rag-lc-embed` / `jmi rag-lc-query` (Worktree B
  deliberately did not ship these — ADR-0015b §10) and retire the custom
  commands.
- **Cost:** the schema-ownership trade is one-shot; the observability loss
  (visible SQL, visible prompt) is permanent and is the main reason this
  ADR votes against the swap as the default.

## Caveats

- **N=15.** The dossier's ±0.10–0.20 noise band is a real upper bound on
  what any retrieval-metric comparison can claim here. A future PR-3.7 can
  scale the seed once the operator has labelled ~50 queries.
- **`langchain-rerank` benchmark is a partial-recovery artifact.** The
  configuration was re-attempted after an Anthropic API outage cluster
  struck mid-debug; the file in `experiments/pr32-benchmark/langchain-
  rerank.md` is the result of the post-outage retry. If the operator wants
  a clean re-run, the standalone runner at
  `experiments/pr32-benchmark/run_from_worktree.py` is one shell line.
- **`langchain-norerank` initial run reported 0.000 across all queries.**
  Cause: the runner's resolver expected `UUID` instances; Worktree B's
  `ScoredChunk.achievement_id` is a string. The fix (one `isinstance`
  guard) landed in the same runner script and produced the 0.587 / 0.700 /
  0.558 numbers in the table. The original zeros are gone; calling this
  out so the morning operator does not trust the first-pass file in any
  git history they happen to inspect.
- **Worktree B's T11 smoke samples are blocked.** The custom side's are
  ready; the LangChain side's were lost to the API outage cluster. A
  re-run on the same vault with the API back online takes ~6 minutes.
- **Bootstrap CIs are not in the table above.** The benchmark JSON
  sidecars (`experiments/pr32-benchmark/*-{json}`) carry per-query vectors;
  feeding them to `jmi.evaluation.retrieval_metrics.bootstrap_ci` (or
  `paired_bootstrap_ci`) recomputes the dossier §3-shaped CI table offline
  in under a second. The morning operator should run that pass before
  quoting any number in the blog post.

## Privacy and qualitative evaluation

Smoke samples (five JD-driven generation runs per pipeline) were
produced during the dual-builder sprint but are intentionally NOT
committed to this public repository. The samples retrieved chunks
from the operator's private career vault — a private GitHub repo
containing real career history (employers, projects, accolades).
Publishing those samples in a public artifact would leak personal
data that the operator has chosen to keep private.

The operator reviewed the samples qualitatively and reported high
satisfaction with both pipelines' output: bullets stayed grounded in
retrieved chunks, citations were correct, and Polish/English
multilingual queries produced coherent generation. No systematic
hallucination patterns were observed across the 10 samples in
informal review.

Formal grounded/partial/hallucinated labeling was deferred:
  1. The corpus is small (10 samples; statistical power negligible).
  2. The smoke samples themselves can't be shared as labeling
     evidence in this repository.
  3. Operator's qualitative pass is the more honest signal at this
     scale than fabricated formal labels.

Future PR-3.4 (the resume generator API/CLI) will exercise the
pipeline on real JDs during operator's own job search, providing
longitudinal qualitative evidence that does not require committing
private career data.

## References

- ADR-0015a — custom RAG implementation
- ADR-0015b — LangChain RAG implementation
- `docs/research/pr-3.2-rag-comparison-dossier.md` — research dossier (§3
  metrics, §5 framework comparison, §6 generation, §7 blog angles)
- `experiments/pr32-benchmark/*.{md,json}` — the four benchmark runs
- `experiments/pr32-benchmark/run_from_worktree.py` — the standalone runner
- `src/jmi/evaluation/{retrieval_seed,retrieval_metrics,benchmark}.py` —
  the eval infrastructure Worktree C shipped
- ADR-0014 — `Achievement` domain + `achievement_embeddings` schema
- ADR-0012 — inline-Protocol repository pattern (used by both sides)
- `docs/roadmap.md` — Phase 3 sub-PR breakdown (PR-3.2 + PR-3.3 collapsed
  into the dual-builder sprint this ADR closes)
