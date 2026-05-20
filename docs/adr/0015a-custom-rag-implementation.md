# ADR-0015a: Custom RAG Implementation (PR-3.2, Worktree A)

**Status:** Proposed — pending PR-3.2 merge. Pairs with ADR-0015b (LangChain
implementation, Worktree B) and the synthesis decision in ADR-0015 (Worktree C).

**Date:** 2026-05-20

**Context of:** the custom RAG pipeline added under `src/jmi/rag/` —
`chunking`, `embedding`, `ingest`, `retrieval`, `reranking`, `pipeline`,
`generation`.

**Companion documents:** `docs/research/pr-3.2-rag-comparison-dossier.md`
(internal research, May 2026) — every recommendation below traces back to a
numbered section there. `docs/phase3-design-constraints.md` (H1/H5/H7).
ADR-0014 (the `Achievement` domain + `achievement_embeddings`).

---

## Context

Phase 3 is JMI's flagship piece — a RAG résumé generator that drafts tailored
bullets from the operator's personal achievement vault. PR-3.1 shipped the
data layer (Achievement model, ORM, repository, ingestion). PR-3.2 ships the
retrieval pipeline.

The roadmap originally split PR-3.2 (custom RAG) from PR-3.3 (LangChain
comparison). This sprint scopes them as a paired effort:

- **Worktree A** (this ADR) — custom RAG against `achievement_embeddings`.
- **Worktree B** (ADR-0015b) — LangChain reimplementation of the same flow.
- **Worktree C** (ADR-0015) — benchmark harness + synthesis decision.

This ADR records the design decisions Worktree A pinned and why. It is *not*
the "custom-versus-LangChain" verdict — that decision lives in ADR-0015 after
both implementations are measured.

## Decisions

### D-1. Chunking — per-section with `[Title — Section]` header

`src/jmi/rag/chunking.py` emits one chunk per non-empty section of an
`Achievement` (`context` / `approach` / `impact` / `lessons`), prepending a
static `[Title — Section]` header to both `chunk_text` (persisted) and
`text_for_embedding` (consumed). Empty sections are skipped; `chunk_index`
is dense from zero.

**Why** — dossier §1.recommendation:

- PR-3.1's parser already split each achievement into the four labelled
  fields. "Per-section" is then "4 fields → 4 chunks," too small to wrap in
  a framework.
- The sections are distinct retrieval facets — a JD that asks for "measurable
  impact" should land on `impact`, one that asks for "ownership" on `lessons`.
  Per-section keeps each facet independently retrievable.
- Section-sized chunks (~75–270 tokens) sit inside both MiniLM's 256-token
  cap and BGE's 512-token cap — no silent truncation.
- The header is free Contextual-Retrieval-style grounding: Anthropic's
  Contextual Retrieval data showed prepended context cut top-20 failures by
  35% — a static title-and-section header captures most of that benefit at
  zero LLM cost.

**Alternative considered.** Sliding window with overlap (dossier §1.c).
Rejected as the primary — it discards the corpus's deliberate four-section
structure and crowds top-K with near-duplicate adjacent windows. Tested as a
controlled mini-experiment (T9, see below) so the decision is empirical, not
just argued.

### D-2. Embedder — `BAAI/bge-small-en-v1.5` (384-dim)

`src/jmi/rag/embedding.py` wraps `BAAI/bge-small-en-v1.5` behind a
two-method `embed_documents` / `embed_query` interface deliberately shaped
like LangChain's `Embeddings` ABC.

**Why** — dossier §2.recommendation:

- 384-dim — a drop-in match for the existing `Vector(384)` column on
  `achievement_embeddings` (ADR-0014). Upgrading MiniLM → BGE-small is a
  re-embed, not a schema migration.
- A clear step up over MiniLM (~+6 MTEB English average), still free, local,
  CPU-fast, and the 512-token window halves truncation risk relative to
  MiniLM's 256.
- Static header keeps the asymmetric instruction prefix out of the
  query/document path for now — flipping it on (the bge-recommended
  `"Represent this sentence for searching..."` prefix) is left as a
  documented one-line seam (`_QUERY_INSTRUCTION` in `embedding.py`).

**`analytics/embed.py` stays MiniLM.** Phase 2 clustering does not benefit
from BGE; coupling the analytics module to the BGE upgrade would change a
second variable. RAG embeddings get their own module.

### D-3. Storage — write through `AchievementEmbeddingRepository`

`src/jmi/storage/achievement_embeddings.py` adds a typed Pydantic ↔ ORM
boundary mirroring `AchievementRepository`. The write path is "delete every
chunk for `achievement_id`, then insert" — UNIQUE(achievement_id,
chunk_index) stays satisfied across re-ingest without an `ON CONFLICT`
clause, and the corpus is small enough that per-row upsert detail would not
pay back.

**Why** — keeps the existing repository style (ADR-0012 inline Protocols),
makes `ingest_embeddings` idempotent by construction, and exposes a clean
seam for the retriever to consume.

### D-4. Retriever — explicit `cosine_distance` ORDER BY in SQL

`src/jmi/rag/retrieval.py` runs an explicit
`ORDER BY embedding <=> :q LIMIT :k` against `achievement_embeddings`
through SQLAlchemy core. The pgvector distance operator is visible at the
call site. Results carry cosine *similarity* (`1 - distance`) so callers
never have to remember sign conventions.

**Why** — dossier §5:

- The visible SQL is part of the value of the custom implementation. It is
  the concrete exhibit for the blog post's "what LangChain's
  `similarity_search` hides" point.
- A Python-side `[:k]` slice is layered on top of the SQL `LIMIT` —
  defense-in-depth + makes stub-session unit tests trivial.

### D-5. Reranker — `BAAI/bge-reranker-base`, drop-in optional stage

`src/jmi/rag/reranking.py` adds a cross-encoder reranker. The pipeline
composer (`pipeline.py`) accepts `Reranker | None`; the default is "on" for
the benchmark and a `--no-rerank` CLI flag disables it.

**Why** — dossier §4:

- 24–80 chunks is a small candidate space — top-5 is most of the corpus —
  so the recall@5 gain will likely fall *inside* the §3 noise band.
- But the seam is the point: the blog post line "we left reranking out of
  the first cut, here is where it would plug in" needs the seam to exist,
  and the LangChain comparison hinges on
  `ContextualCompressionRetriever` as the foil. Worktree A ships the
  reranker on by default so the benchmark can measure it as its own
  experiment.
- An empty input is a fast pass-through. A single-chunk input still hits
  the cross-encoder so the returned `score` is uniformly the cross-encoder
  logit — callers never need to ask which stage produced the score.

### D-6. Generation — Anthropic SDK direct, prompt-as-literal-string

`src/jmi/rag/generation.py` calls Claude (default `claude-opus-4-7`) via the
Anthropic SDK. The system prompt is a literal multi-line string in the
module — auditable, quotable, and version-controlled with the code.

**Why** — dossier §5 / §6:

- LCEL's wins (streaming, retries, batching) do not apply to a *single* call
  where the prompt itself is the product. The deliverable is the prompt
  and the bullets it produces, not the chain plumbing.
- The system prompt encodes the five dossier §6 rules: role,
  hallucination guard, JD-grounding, citation, lessons usage. Every bullet
  must trace to one or more numbered chunks via a `(chunks: 1, 3)` tag —
  the audit trail is in the output.
- `GenerationResult` carries the `chunk_ids_in_prompt` list so a downstream
  consumer (T11 smoke check, future evaluation) can verify citation
  faithfulness without re-parsing the prompt.

### D-7. Top-K and candidate pool

- **Top-K = 5** for the benchmark. Match-to-generation (dossier §6) — the
  retrieved chunks are literally what the generator sees, so K is the cap
  on output quality.
- **Candidate pool = 3·K = 15** when reranking. Gives the cross-encoder
  room to reorder without bloating prompt cost; the pool is an explicit
  argument to `retrieve_top_k` so the benchmark can vary it.

### D-8. Logging — H7/O-4 names, no chunk body

Every stage emits a structured event named `rag.{stage}.{outcome}` —
`rag.chunk.done`, `rag.embed.batch.done`, `rag.ingest.achievement.done`,
`rag.retrieve.done`, `rag.rerank.done`, `rag.generate.start` /
`rag.generate.done`.

Per H1/S-2, no event carries chunk body. Logged fields are ids, counts,
durations, slugs, token counts, and a 12-char `prompt_id` SHA prefix that
ties `rag.generate.start` to its matching `rag.generate.done` for
traceability across the LLM call.

### D-9. CLI surface — two commands

- `jmi rag-embed [--achievement-id …]` — chunk and embed, idempotent
- `jmi rag-query "<text>" [--k N] [--no-rerank]` — retrieve and print top-K

Generation (T7) does not get a CLI in PR-3.2 — the smoke-check experiment
(T11) drives it for now, and a `jmi cv-draft` style command lands in PR-3.4
with the full résumé generator UX.

## Cross-references to the dossier

| Section | Dossier reference |
|---|---|
| D-1 chunking | §1.recommendation |
| D-2 embedder | §2.recommendation + §2 (no 384→768 migration) |
| D-3 storage  | §3 chunk-vs-document rollup |
| D-4 retriever | §5.PGVector — observability wins |
| D-5 reranker | §4 — defer / drop-in seam |
| D-6 generation | §5.LangChain steelman + §6 prompt shape |
| D-7 top-K | §6 — recall caps generation quality |
| D-8 logging | H7/O-4 + H1/S-2 |
| Blog angle | §7 — Angle A "I built RAG twice" with §C's CI spine |

## Mini-experiments (in worktree A, separate sub-branches)

- **T9 — sliding-window chunker** (`feat/phase3-pr3.2-A-sliding`).
  Re-implements chunking as 256-token windows with 64-token overlap (cl100k_base
  via tiktoken). Re-ingests, re-runs the benchmark (Worktree C). Documents the
  delta vs per-section. Hypothesis (dossier §1.c): degrades retrieval because
  windows straddle the four-section structure the corpus deliberately has.

- **T10 — Polish dual-embedding routing**
  (`feat/phase3-pr3.2-A-multilingual`). Adds a second embedder using
  `intfloat/multilingual-e5-small` (384-dim, drop-in column). Detects query
  language with `langdetect`; routes Polish queries to the multilingual
  model, English to BGE. Stores `embedding_model_name` per chunk via an
  Alembic migration so both embedding sets coexist. Tests on
  Claude-translated Polish versions of the seed queries. Hypothesis (dossier
  §2.e): the multilingual routing materially improves recall on Polish
  queries with minimal English regression.

Both sub-branches return to `feat/phase3-pr3.2-A` after documenting the delta
in their own commit.

## Consequences

### Positive

- Every piece of the pipeline is a small Python module with a clean
  Protocol-shaped seam — the embedder, the reranker, and the repository all
  swap without touching their callers (essential for T10 and Worktree C's
  benchmark).
- The custom code reuses the ADR-0012 inline-Protocol pattern and the
  ADR-0011 `Vector(384)` schema with zero migration.
- The pgvector SQL stays visible — pedagogically valuable, blog-quotable,
  and easy to `EXPLAIN`.
- The generation prompt is a literal string in the repo with explicit
  citation rules — auditable now, ready for the evaluation framework (PR-3.7).

### Negative

- BGE adds a model dependency Phase 2 did not have (~130 MB download).
  Lazy-loaded so import time is unchanged; the first call pays the model
  load.
- The reranker is a second model dependency (~280 MB). Optional via
  `--no-rerank`, but on by default for the benchmark — the recall@5 gain at
  24–80 chunks is likely inside the noise band (dossier §4) and the reranker
  must justify its weight in ADR-0015.
- "Delete-then-insert" replace strategy is simple but issues O(chunks)
  inserts per achievement. Fine at corpus size ~50; would need batched
  insert if the vault grew an order of magnitude.

### Neutral

- The dossier explicitly predicts custom-vs-LangChain differences will sit
  inside the noise band at N≈15 (§3). The intellectual-honesty framing of
  ADR-0015 / the blog spine (§3 + §7) is built into the synthesis ADR's
  design rather than this one.

## Alternatives Considered

a. **Per-document chunking.** Plus: simpler, recall@k = document recall by
   construction. Minus: silently truncates 300–800-word achievements under
   MiniLM's 256-token cap; even with BGE's 512 cap it averages four sections
   into one blurred vector. Dossier §1.b. **Rejected.**

b. **Late chunking (Jina).** Plus: every chunk embedding carries
   full-document context. Minus: requires a long-context model exposing
   token-level outputs (`jina-embeddings-v2/v3`); replaces the whole embedding
   stack; the problem it solves is small at 300–800-word documents. Dossier
   §1.e. **Noted, not adopted.**

c. **OpenAI `text-embedding-3-small` (Matryoshka 384-dim).** Plus: strong
   MTEB; per-call cost essentially zero. Minus: adds an API dependency and
   sends personal achievements to a third party — breaks the
   free/local/deterministic property ADR-0011 valued. Dossier §2.f.
   **Rejected.**

d. **PGVector via LangChain `PGVectorStore`.** This is what Worktree B
   tries. Plus: less code in the greenfield case. Minus: it owns its own
   schema (`langchain_pg_collection` / `langchain_pg_embedding`) — adopting
   it for JMI means either a second embeddings table without an FK to
   `achievements`, or a custom `VectorStore` subclass (at which point you
   have written the custom code anyway). The schema-collision finding is
   dossier §5's sharpest. **Out of scope for Worktree A by definition.**

e. **LCEL chain for generation.** Plus: declarative composition; streaming,
   retries, and batching for free. Minus: a single call where the prompt is
   the product gains nothing from those features; hides the actual request
   shape. **Rejected for PR-3.2 — direct SDK.**

## References

- Dossier — `docs/research/pr-3.2-rag-comparison-dossier.md`
  (§1 chunking · §2 embedder · §3 metrics · §4 reranker · §5 LangChain
  surface · §6 generation · §7 blog angle).
- Design constraints — `docs/phase3-design-constraints.md`
  (H1/S-2 logging · H5/E-1 metrics · H7/O-4 events).
- ADR-0011 — Phase 2 PoC choices (the `all-MiniLM-L6-v2`/`Vector(384)` baseline
  this PR keeps the schema of).
- ADR-0012 — Inline-Protocol repository pattern (the storage shape this PR
  follows).
- ADR-0014 — Achievement domain + `achievement_embeddings` table.
- ADR-0015b *(pending)* — LangChain reimplementation.
- ADR-0015 *(pending)* — Custom-vs-LangChain synthesis.
- Roadmap — `docs/roadmap.md` (PR-3.2 + PR-3.3 → paired sprint).
