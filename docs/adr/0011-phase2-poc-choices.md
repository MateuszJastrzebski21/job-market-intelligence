# ADR-0011: Phase 2 Analytics PoC — Embeddings, Clustering, Reporting

**Status:** Accepted
**Date:** 2026-05-18
**Context of:** Phase 2 analytics PoC (`src/jmi/analytics/`, the `jmi analyze` command)

## Context

Phase 1 delivered a ToS-clean ingestion pipeline: postings are scraped or
HITL-ingested, then a separate pass runs LLM extraction (ADR-0006). PR18 opens
Phase 2 by adding the first *downstream* layer — a way to look at the corpus as
a whole rather than one posting at a time. The roadmap scopes this as a
proof-of-concept: embed postings, cluster them, and emit a shareable report.
The goal is a correct, re-runnable pipeline, not market intelligence at scale —
the Mac database currently holds only 18 postings. This ADR records six choices
made for that PoC so a future reader does not mistake deliberate PoC
constraints for defects.

## Decision

### 1. Embedding model — sentence-transformers/all-MiniLM-L6-v2

Embeddings are produced locally by `all-MiniLM-L6-v2` (384 dimensions). It is
free, runs on CPU, needs no API key, and its quality is adequate for a corpus
well under a thousand documents. The one-time ~90 MB model download is cached
locally and is not a metered API call — PR18 spends nothing on inference.

Embeddings are computed **per posting, not per extract**, and the `vector(384)`
column lives on `job_postings`. An embedding is a fact about the posting's own
text (title + description); it does not depend on LLM extraction having
succeeded. This keeps analytics aligned with the separated pipeline of
[ADR-0006: Extraction Pipeline Architecture](0006-extraction-pipeline-architecture.md):
embedding is its own downstream stage, decoupled from extraction, and it lets
all 18 postings participate in clustering rather than only the 7 that currently
have an extract. The embedded text is `title + "\n\n" + description_text` — raw
posting text, because the structured extract is a lossy projection and
embedders work better on natural language.

### 2. Clustering — KMeans with a fixed k = 6

Clustering uses scikit-learn KMeans with `k = 6` fixed — not HDBSCAN, not an
elbow- or silhouette-tuned k. KMeans is interpretable and, with a fixed
`random_state`, deterministic, so re-runs are reproducible. `k = 6` is a
deliberate proxy for six rough AI/ML role archetypes (research, applied, MLOps,
full-stack AI, data, lead) and is held constant regardless of N. The trade-off
is that structure is forced even when the data does not support six groups; the
silhouette score is logged on every run to make that visible (see §6).

### 3. Dashboard — single-file HTML with Chart.js via CDN

The visual report is one self-contained HTML file that pulls Chart.js from a
CDN and renders a bar chart of cluster sizes and a pie chart of sources. This
needs zero infrastructure and produces a shareable static artifact, matching
the roadmap anti-goal of "no deploy before Phase 5". The trade-off is no
interactivity beyond Chart.js defaults; a Streamlit or web-app dashboard is
explicitly deferred.

### 4. Markdown report as the committed companion

`jmi analyze` writes a Markdown report alongside the HTML. Markdown renders
natively on GitHub, diffs cleanly across re-runs, and is a usable source for
later blog-post material. To avoid duplicated formatting logic, both renderers
share one computation function (`_build_report_data`). Only the **Markdown**
report is committed to the repository, as the GitHub-rendered artifact; the
**HTML** file is a local build and is git-ignored. Committing a styled HTML
dashboard populated with real posting data would amount to the "public
dashboard with my data" the roadmap rules out.

### 5. Analytics consumes the pipeline; it does not re-run it

The analytics layer only reads existing pipeline outputs — postings for
embeddings, extracts for the per-cluster tech-stack view. It never re-scrapes
or re-extracts. This is the same separated-pipeline discipline as ADR-0006:
analytics is a downstream consumer. Embeddings are written once and stored, so
`jmi analyze --skip-embed` can re-cluster and re-render cheaply without
recomputing them. The repository queries that feed clustering order rows by
`(scraped_at, id)` — a total order — so KMeans always receives the same input
sequence and `jmi analyze` is reproducible run to run, including across
`--skip-embed`.

### 6. PoC scale — N = 18, k = 6 (the honest caveat)

This PoC runs on the 18 postings currently in the Mac database. `k = 6` is held
fixed as the role-archetype proxy of §2, independent of N. At N = 18 that is
roughly three postings per cluster, so the silhouette score is expected to be
low — the first PoC run scored 0.18, below the 0.2 "weakly separated"
threshold. Clustering logs a warning below 0.2 and an error below 0.1 but never
fails; the PoC's value is pipeline correctness, not the clusters themselves. The first statistically meaningful
clusters are expected only after a re-run at N > 50. This section exists so a
future reader does not look at a noisy report and conclude the clustering is
broken: at N = 18 it is simply small-sample. (The PC database holds ~57
postings; reconciling the two machines is an unsolved multi-machine sync
problem, out of scope here.)

## Consequences

### Positive

- First downstream layer over the corpus; a demo-ready, shareable artifact.
- Zero API cost and zero infrastructure — embeddings are local, the dashboard
  is a static file.
- Embeddings stored on `job_postings` are reusable by later phases (e.g. the
  Phase 3 RAG retrieval layer) without recomputation.
- Deterministic and re-runnable: fixed `random_state`, plus `--skip-embed` for
  cheap re-rendering.

### Negative

- `all-MiniLM-L6-v2` has lower semantic resolution than paid embeddings
  (Voyage, OpenAI text-embedding-3); acceptable at PoC scale, revisit at N > 500.
- A fixed `k` forces six clusters even when the data has no such structure.
- At N = 18 the report is not market intelligence; its clusters should not be
  read as findings.

### Neutral

- `sentence-transformers` pulls in `torch`, materially enlarging the install;
  acceptable for a local analytics tool.
- No approximate-nearest-neighbour index on the `embedding` column — clustering
  reads every vector into memory, which is fine at this scale and revisited only
  if similarity search is ever needed.

## Alternatives Considered

a. **HDBSCAN / density clustering instead of KMeans.** Plus: discovers the
   cluster count and marks outliers. Minus: less interpretable, non-deterministic
   to tune, overkill at N = 18. When: reconsider once N is large enough for the
   cluster count to be a real question.

b. **Paid embeddings (Voyage, OpenAI text-embedding-3).** Plus: higher semantic
   quality. Minus: API cost and a key dependency for what is a free, local PoC.
   When: revisit at N > 500, as its own benchmarking PR.

c. **Streamlit or a web-app dashboard.** Plus: interactivity. Minus: needs a
   running process and, eventually, a deployment — both against the "no deploy
   before Phase 5" anti-goal. When: Phase 5.

## References

- [ADR-0005: Structured Output Approach](0005-structured-output-approach.md) — the extract schema this analytics layer sits downstream of.
- [ADR-0006: Extraction Pipeline Architecture](0006-extraction-pipeline-architecture.md) — the separated-pipeline principle this ADR extends to embeddings.
- [ADR-0010: Evaluation Framework](0010-evaluation-framework.md) — the sibling downstream package whose structure (`runner.py`, `schemas.py`) `analytics/` mirrors.
- `docs/roadmap.md` — Phase 2 scope and the PR18 specification.
- `docs/competitive-landscape.md` — project positioning: evaluation rigor and documented decisions over scraper breadth.
