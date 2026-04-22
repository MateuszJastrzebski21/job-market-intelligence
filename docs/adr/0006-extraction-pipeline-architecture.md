# ADR-0006: Extraction Pipeline Architecture — Separated, Not Inline

**Status:** Accepted
**Date:** 2026-04-22
**Context of:** Week 1 LLM extractor (`jmi extract` CLI) vs Week 1 HF scraper (`jmi scrape`)

## Context

The pipeline has two distinct stages:
1. **Scrape** — fetch raw postings from a portal (HF / JJIT / NoFluffJobs) → `JobPosting`
2. **Extract** — LLM-structure each posting → `JobExtract`

Two shapes are viable:

- **Inline:** `jmi scrape` fetches a posting, extracts it, saves both rows in
  one DB transaction. One process, one loop.
- **Separated:** `jmi scrape` saves `JobPosting` rows only. A separate
  `jmi extract` command later reads un-extracted postings and writes
  `JobExtract` rows.

## Decision

**Separated pipeline.** `jmi scrape` saves only raw postings; `jmi extract` is
a standalone command that reads postings without an extract for the current
model and writes `JobExtract` rows.

## Consequences

**Positive**

- **Re-extract without re-scrape.** When we iterate the prompt (Phase 3
  eval framework) or swap models (A/B Opus 4.7 vs Haiku 4.5 vs Sonnet 4.6),
  we re-run only the extractor against the existing `job_postings` rows.
  Scraping a portal again risks rate limits, anti-bot pushback, and
  duplicates detection logic churn.
- **Failure containment.** A Workable 429 or Playwright timeout doesn't
  block LLM extraction of the postings we already have. An Anthropic
  5xx doesn't block scraping new postings.
- **Batch API readiness.** Phase 5 optimization switches extract to the
  Messages Batches API (50% cost, async). Batch is inherently async and
  deferred — inline scrape-and-extract can't use it without restructuring.
  Separated pipeline already matches the batch shape: collect inputs,
  submit, poll results.
- **Cost attribution.** Scrape cost (network only) and extract cost
  (Anthropic tokens) stay separate in logs. When a user asks "why did
  my bill jump?" we can answer.
- **Independent scaling.** If Phase 2+ we switch extract to async/batch
  while scrape stays sync, the pipelines don't fight each other.

**Negative**

- **Two commands to run** for a fresh end-to-end result. Mitigation: a
  future `jmi run-all` convenience wrapper, or cron chaining.
- **Intermediate state visible in DB.** A posting without its extract is
  a valid state, not an error. Queries that assume "every posting has
  an extract" must JOIN carefully. Acceptable — it's the truth.
- **Slightly more code.** Two CLI commands + two repositories exercised.
  We already have both repositories; negligible extra code.

## Alternatives Considered

### Inline (scrape → extract → save in one loop)

- **Plus:** Single command, immediate full result. Fewer rows in an
  "incomplete" state at any moment.
- **Minus (decisive):**
  - **Re-extraction is structurally impossible** without re-scraping.
    We throw away the decoupling that the `job_postings` / `job_extracts`
    table split was designed to give us (decided in Week 1 schema design).
  - Cascading failure: a single Anthropic 5xx kills the scrape run
    mid-portal. Resuming means either tracking scrape cursor separately
    or re-scraping from zero.
  - Can't batch extracts. Phase 5 switch to Batch API would require
    deleting this architecture entirely.
  - Blurs cost attribution — one long-running command with two cost
    profiles.
- **When inline would make sense:** one-shot tools for tiny datasets
  where retention isn't a goal. Our project is explicitly about
  building a queryable history and re-running analytics as models
  improve — exactly the opposite use case.

### Queue-based (Redis/RabbitMQ between scrape and extract)

- **Plus:** True producer/consumer isolation, horizontal scaling.
- **Minus:** Massive overkill at our scale (tens-to-hundreds of
  postings/day). Adds a broker to deploy and monitor for zero benefit.
- **When to pick:** Phase 5+, if throughput outgrows a simple
  `ORDER BY scraped_at` scan on the DB, or we parallelize extract
  across workers.

## Consequences for Code Today

- `HuggingFaceScraper.run()` (done) writes only `JobPosting`. It does
  **not** call the extractor.
- `AnthropicExtractor.run()` (this week) takes `JobPostingRepository` +
  `JobExtractRepository`, iterates postings without an extract for
  `self.model`, writes `JobExtract`.
- CLI stays split: `jmi scrape`, `jmi extract`.

## References

- Schema split decision — see `src/jmi/db/models.py` (`job_postings` /
  `job_extracts` two-table layout from Week 1).
- Anthropic skill: `python/claude-api/batches.md` — Batch API shape
  that separated pipeline maps onto cleanly.
