# Phase 3 Design Constraints — Security, Retrieval Evaluation, Observability

**Status:** Specification — constraints to design into Phase 3, not yet implemented.
**Date:** 2026-05-18
**Source:** 2026-05-18 codebase audit (`docs/audit-2026-05-18.md`) — issues
H1 (#24), H5 (#28), H7 (#30).
**Applies to:** Phase 3 — RAG résumé generator, PR-3.1 through PR-3.7 (`docs/roadmap.md`).

## Why this document exists

Phase 3 introduces one new risk class and two new quality surfaces that the Phase 1–2
foundation was never designed for:

- it ingests the **operator's real personal career history**, not public job postings;
- its core mechanism — retrieval of achievement chunks — has **no measurement** in the
  current evaluation package;
- it spans **6+ new modules** whose instrumentation must be uniform from the first PR.

The audit found all three are cheap to design in now and expensive to retrofit. This is
the binding constraint set for PR-3.1 / 3.2 / 3.4. It is a specification: it states
*what must hold*, not *how to implement it*.

---

## 1. Security (audit H1 / issue #24)

**Why:** until Phase 3, every input JMI handled was a public job posting. Phase 3
ingests the operator's personal achievement files and generates documents from them.
Path handling, logging, storage, and prompt construction now all sit on personal data.

### S-1 — Corpus file paths must be sandboxed against traversal

Every achievement-corpus file read (PR-3.1 ingestion) resolves the path and verifies
containment before opening it:

- resolve symlinks and `..` with `Path.resolve()`;
- reject any path that is not `is_relative_to()` the configured `ACHIEVEMENTS_DIR`;
- the achievements directory is a single configured root — nothing outside it is
  readable by the ingestion pass.

A path that fails containment is rejected with a structured error and never opened.

### S-2 — Achievement content must never be logged

Logs are the lowest-friction leak path for personal data. Ingestion, chunking,
embedding, and generation may log **identifiers and titles only**:

- log the achievement file name / chunk id / title — never the body text;
- never log a generated CV bullet or cover-letter paragraph at INFO; DEBUG may log
  lengths and counts, never content;
- error logs scrub content — log the exception type and the chunk id, not the chunk.

### S-3 — Personal embeddings live in a separate, purgeable table

Job-posting embeddings sit on `job_postings` (ADR-0011). Personal-achievement
embeddings must NOT share that table:

- a dedicated `achievement_embeddings` table, droppable without touching job data;
- a documented purge path (one command or migration) that removes all personal
  vectors and their source rows;
- any database backup containing personal data is git-ignored and excluded from every
  artifact that could be published.

### S-4 — Job-posting text is untrusted prompt input (indirect prompt injection)

Phase 3 prompts combine the operator's achievements with job-posting text. Posting text
is attacker-influenced — anyone can write a job ad:

- treat all posting-derived text as untrusted data, never as instructions; keep it in
  clearly delimited input sections of the prompt;
- add an **indirect-prompt-injection canary** to the Phase 3 eval suite — a fixture
  posting whose description carries an injection attempt; the generator must ignore it,
  and a canary failure fails the eval run.

### S-5 — Phase 3 retrieve / generate endpoints require auth

Any Phase 3 HTTP surface (retrieval, CV or cover-letter generation) sits behind
authentication — reuse the `verify_ingest_token` dependency pattern (timing-safe per
H3 / #26) or an equivalent. No unauthenticated endpoint may read or emit personal data.

---

## 2. Retrieval Evaluation Infrastructure (audit H5 / issue #28)

**Why:** evaluation rigor is the project's stated #1 differentiator (`docs/roadmap.md`,
`docs/competitive-landscape.md`). Today the `evaluation/` package measures only
*extraction* accuracy. Phase 3's core mechanism is *retrieval*, and retrieval quality is
currently unmeasurable. It must be measurable from PR-3.2, the first RAG PR.

### E-1 — Ranking-metrics module

A new `evaluation/retrieval_metrics.py` provides the standard ranking metrics:

- **recall@k** — fraction of relevant chunks present in the top *k*;
- **MRR** — mean reciprocal rank of the first relevant chunk;
- **nDCG** — rank-discounted gain for graded relevance.

These are pure functions over `(ranked_ids, relevant_ids)` — no DB, no model — so they
unit-test trivially, mirroring the existing extraction-metrics structure.

### E-2 — Golden retrieval seed schema

A `docs/ground_truth/rag_retrieval_seed.json` file defines retrieval ground truth:

- each entry pairs a query (a job posting or a role) with the set of achievement chunk
  ids that *should* be retrieved for it, plus optional graded relevance for nDCG;
- a Pydantic schema validates the seed file, exactly as `evaluation/schemas.py`
  validates the extraction seed;
- a minimum of ~10 query entries exists before the Phase 3 RAG MVP merges.

### E-3 — Deterministic embedding fixtures

Retrieval tests must not depend on a live embedding model — it is slow and not
deterministic across versions:

- provide canned, fixed embedding vectors for the test corpus;
- a retrieval test run is fully deterministic and offline;
- the real embedding model is exercised separately in a marked `slow` / `integration`
  test (audit M6).

### E-4 — Shared test fakes

The audit found four ad-hoc in-memory fake-repo classes copy-pasted across test files.
Phase 3 must not add a fifth:

- consolidate fakes into a shared `tests/fakes.py`;
- the new `AchievementRepository` fake lives there, beside the existing posting and
  extract fakes, all matching the inline-Protocol pattern (ADR-0012).

---

## 3. Observability (audit H7 / issue #30)

**Why:** Phase 3 is 6+ new modules — ingestion, chunking, embedding, retrieval,
generation, evaluation. If instrumentation is added per module ad hoc it will be
inconsistent and have to be retrofitted across all of them. The conventions below are
fixed once, here, before the modules are written.

### O-1 — Per-stage timing

Each RAG pipeline stage (chunk, embed, retrieve, generate) emits a structured timing
event carrying a `duration_ms` field. A full generation request is reconstructable from
its stage timings.

### O-2 — Embedding and generation cost tracking

Every embedding batch and every LLM generation call records token counts **and** a
`cost_usd_estimate`. This closes audit M8 — today only token counts are tracked, with no
USD figure — and extends it to embeddings. Cost is queryable per run.

### O-3 — Eval runs are persistent, not ephemeral

Today eval results print to stdout and vanish. Phase 3 retrieval-eval runs are written
to a durable, append-only location (e.g. `docs/eval_runs/{timestamp}.json`) so quality
is a trend, not a single screenshot. Each run records the metric values, the seed-file
version, and the embedding-model id.

### O-4 — structlog event-naming convention

One documented event-naming convention, applied across every Phase 3 module:

- dotted `{domain}.{action}[.{outcome}]` — e.g. `rag.retrieve.done`, `rag.embed.failed`
  — consistent with existing events such as `extract.done` and `extract.refused`;
- a short table of the Phase 3 event names is maintained in this section as modules land.

### O-5 — Request-scoped context binding

Every Phase 3 API request binds a `request_id` into the structlog context at the
middleware level (audit L10), so all log lines for one request are correlatable; every
downstream stage event inherits it.

---

## Acceptance

This specification is satisfied when:

- PR-3.1 ships S-1, S-2, S-3 and the `achievement_embeddings` table;
- PR-3.2 ships E-1, E-3, E-4 and the retrieval metrics, plus O-1;
- PR-3.4 ships S-4 (including the injection canary), S-5, and O-2;
- E-2 (the retrieval seed) and O-3 / O-4 / O-5 are in place before the Phase 3 RAG MVP
  (PR-3.1 + 3.2 + 3.4) is declared merged.

Any deviation is recorded as an ADR, not made silently.
