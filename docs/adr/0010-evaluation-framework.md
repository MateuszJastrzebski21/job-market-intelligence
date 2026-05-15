# ADR-0010: Extraction Quality Evaluation Framework

**Status:** Accepted
**Date:** 2026-05-15
**Context of:** PR16 — first objective measurement of extraction quality

## Context

The extractor has produced 19 `JobExtract` rows via Claude Opus 4.7. A manual
quality investigation (`docs/next-session.md`, commit `6d466a4`) eyeballed a
10-job sample and found:

- `tech_stack` ~8/10, `seniority` ~8/10, `remote_policy` ~9/10 — healthy.
- `salary` ~2/10 — a **critical bug**: a posting stating
  `"Stawka: do 145 PLN/h"` extracted `salary_min/max/currency = NULL`.

These numbers are subjective. There is no repeatable, objective metric, so we
cannot say whether a prompt change actually helps — only that it "feels"
better. PR1 (`b35f679`) anticipated this: the ground-truth seed file was
created so *"the Phase 3 eval framework so we aren't starting from zero"*.

We are about to iterate the prompt (PR17) and re-extract (PR18). Doing that
without a measurement layer means flying blind.

## Decision

Build a dedicated **`src/jmi/evaluation` package** that compares extracts
against the ground-truth seed file and reports per-field metrics, exposed as
a `jmi evaluate` CLI command.

- **Baseline-only.** PR16 measures; it does not touch the extractor, the
  prompt, the seed file, or existing extracts.
- **Separated from extraction.** Measurement is its own package, mirroring the
  scrape/extract separation of ADR-0006. The evaluator reads `job_postings`
  and `job_extracts`; it never writes.
- **Repository-injected, fake-testable.** The runner takes repository objects,
  not a `Session`, so its logic is unit-tested against in-memory fakes —
  consistent with the rest of the test suite.

## Consequences

**Positive**

- **A/B prompts become measurable.** PR17 changes the prompt; `jmi evaluate`
  before and after quantifies the delta instead of guessing.
- **A/B models become measurable.** Re-extract with Haiku 4.5 / Sonnet 4.6 and
  compare per-field accuracy.
- **Drift detection.** Re-running evaluation after any extractor change
  surfaces regressions.
- **Separation of concerns.** Measurement code cannot accidentally mutate
  extraction state — the evaluator has no write path.

**Negative**

- **No data to score yet.** The seed currently holds 3 id-only HuggingFace
  few-shot entries, which the framework reports as unmatchable. The framework
  ships ahead of the labelled dataset; manual labelling is follow-up work.
- **Ground-truth labelling is manual and subjective.** The metric is only as
  good as the labels. `tech_stack` in particular is interpretation-heavy.

### Expected baseline (forecast)

Eyeballed hypotheses from the manual investigation, to be **confirmed after
the first run on a labelled seed**. Recorded here so the first real numbers
can be checked against intuition:

- `seniority`: ~80–90%
- `remote_policy`: ~85–95%
- `tech_stack` Jaccard avg: ~0.65–0.75
- `salary_min` recall: ~10–15% — the PR17/18 improvement target
- `salary_currency` match: ~10–15%

These are not commitments; they are a sanity baseline.

## References

- ADR-0005 — structured-output approach (the `JobExtractSchema` boundary the
  evaluator scores against).
- ADR-0006 — separated scrape/extract pipeline; this ADR extends the same
  separation principle to measurement.
- PR1 commit `b35f679` — created `phase1_seed.json` explicitly to seed this
  framework.
- `docs/evaluation_methodology.md` — metric definitions and how to read the
  report.
