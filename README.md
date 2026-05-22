[![CI](https://github.com/MateuszJastrzebski21/job-market-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/MateuszJastrzebski21/job-market-intelligence/actions/workflows/ci.yml)

# Job Market Intelligence

*Personal AI/ML job-market intelligence for the Polish market — ToS-clean
ingestion, a measurable evaluation framework, custom RAG planned.*

---

## What this is

**Job Market Intelligence (JMI)** is a personal AI/ML job-market pipeline for the
Polish market. It ingests job postings from three sources, extracts structured
fields with an LLM, stores them in Postgres, and turns them into market analytics.
JMI is built as two things at once: a working personal tool, and a portfolio
project demonstrating production-minded AI engineering — evaluation, ToS
discipline, and documented decisions.

```
ingest  ──▶  extract  ──┬──▶  evaluate   (measure extraction quality, per field)
                        │
                        └──▶  analyze    (embeddings, clustering, market report)
```

The pipeline runs in four stages:

1. **Ingest** — collect raw job postings into a single `JobPosting` table. Every
   source feeds the same table and the same downstream pipeline, so adding a source
   never forks the processing path.
2. **Extract** — an LLM reads each posting and returns structured fields —
   seniority, tech stack, salary, remote policy — as validated Pydantic models.
   Extraction uses prompt caching to cut token cost, tracks per-run token usage,
   and guards against model refusals so a refused call never persists as a silent
   empty record.
3. **Evaluate** — extraction quality is measured per field against a hand-labelled
   ground-truth set: Jaccard similarity on tech-stack lists, recall on salary
   capture, exact match on seniority. A prompt change is judged by the numbers it
   moves.
4. **Analyze** — sentence-transformer embeddings and KMeans clustering turn the
   extracted corpus into a market report, written as both Markdown and a
   single-file HTML dashboard.

Phase 3 will add a fifth stage: a RAG résumé generator that tailors CV bullets to a
specific posting from a personal achievement corpus.

### Data sources

| Source | Type | Ingestion path |
|---|---|---|
| Hugging Face Jobs | Public API | Direct API scraper (`jmi scrape`) |
| JustJoinIT | Polish IT portal | HITL Chrome extension |
| NoFluffJobs | Polish IT portal | HITL Chrome extension |

All three are ToS-clean. The section below explains why two of them are ingested
through a browser extension rather than scraped server-side.

## What this is not

JMI is not a novel concept, and this README does not pretend otherwise. Job
scrapers, LLM extraction, and résumé tooling all exist independently. The value
here is the *combination* and the *execution*.

To be explicit about scope:

- **Not a general-purpose job aggregator.** The focus is deliberately narrow —
  Polish AI/ML roles, for a single user.
- **Not an auto-applier.** A later phase adds an apply agent, but every submission
  stays human-in-the-loop; the agent never sends an application on its own.
- **Not a server-side scraper of portals that forbid it.** Postings from Polish
  portals are captured in the user's own browser session, not pulled by the
  backend.
- **Not a hosted product.** It is a single-user system — no accounts, no billing,
  no team features.

## What makes this different

The differentiation is in execution, not concept. Five things, drawn from a
[competitive-landscape review](docs/competitive-landscape.md) that compared JMI
against the closest open-source projects:

### ToS-clean, human-in-the-loop ingestion

Polish job portals (JustJoinIT, NoFluffJobs) prohibit automated server-side
extraction in their terms of service. Instead of ignoring that, JMI ingests them
human-in-the-loop: a Chrome MV3 extension captures postings the user is already
viewing in their own browser session and posts them to a local FastAPI endpoint —
the backend never scrapes those portals itself. Hugging Face Jobs, which exposes a
clean public API, is scraped directly. The reasoning and the rejected alternatives
are documented in [ADR-0008](docs/adr/0008-jjit-removed-from-phase-1.md) and
[ADR-0009](docs/adr/0009-hitl-ingestion-pivot.md).

### A measurable evaluation framework

Extraction quality is measured, not assumed. The evaluation package scores each LLM
extraction against ground-truth labels field by field — Jaccard similarity for
tech-stack lists, recall for salary capture, exact match for seniority — so a
prompt change can be judged by a number instead of a vibe. `jmi evaluate` runs it
against a labelled seed set. Evaluation rigor is the project's stated primary
differentiator, and the same discipline is planned for measuring retrieval quality
in Phase 3. The methodology is in
[`docs/evaluation_methodology.md`](docs/evaluation_methodology.md) and the design
rationale is in [ADR-0010](docs/adr/0010-evaluation-framework.md).

### A deliberately narrow niche

JMI covers Polish AI/ML roles specifically — a market with little coverage in
comparable open-source job-analysis projects, and the market the author is actually
hiring into. That keeps JMI a tool in real use rather than only a demo, and keeps
the extraction prompts, evaluation labels, and analytics sharp rather than diluted
across every country and role type.

### Decisions recorded as ADRs

Non-trivial choices are written down as Architecture Decision Records before the
code is built — what was decided, why, and what was rejected. Writing the ADR
first shapes the implementation rather than rationalising it afterwards. The 7 ADRs
in [`docs/adr/`](docs/adr/) cover the extraction-pipeline architecture, the
structured-output approach, the HITL ingestion pivot, the evaluation framework, and
the repository pattern.

### Custom RAG planned — with a framework comparison

Phase 3's retrieval layer will be built from scratch — chunking, embeddings,
retrieval — rather than assembled from a framework. A LangChain reimplementation is
then planned as a deliberate side-by-side comparison, with an ADR documenting the
trade-offs. Building it twice is the point: it surfaces what a framework abstracts
away, and what that abstraction costs.

## Quick start

**Prerequisites:** [Docker](https://www.docker.com/) (for local Postgres) and
[uv](https://docs.astral.sh/uv/) (Python package manager). uv installs Python 3.12
for you.

```bash
# 1. Install dependencies into a virtualenv
uv sync

# 2. Create your .env from the template
cp .env.example .env

# 3. Start Postgres 15 + pgvector
docker compose up -d

# 4. Create the database schema (Alembic migrations)
uv run jmi init-db
```

Then drive the pipeline with the `jmi` CLI:

```bash
# Ingest postings from the Hugging Face Jobs API
uv run jmi scrape --source huggingface --limit 50

# Run LLM extraction on postings that don't have an extract yet
uv run jmi extract --limit 50

# Score extraction quality against ground-truth labels
uv run jmi evaluate

# Embed + cluster the corpus and write Markdown + HTML reports
uv run jmi analyze --output report

# Serve the FastAPI ingest endpoint the Chrome extension posts to
uv run jmi serve
```

### Resume generation (PR-3.4)

Once achievements are ingested (`jmi ingest-achievements`) and embedded
(`jmi rag-embed`), generate a tailored markdown resume + cover letter from
a JD:

```bash
# Inline JD, English-language, with web research and a conversational tone
uv run jmi generate-resume --jd-text "$(cat path/to/jd.txt)"

# JD from file, output to a markdown file + full JSON audit
uv run jmi generate-resume \
    --jd-file path/to/jd.txt \
    --output out/resume.md \
    --json out/resume.json

# Estimate cost before running (no API calls)
uv run jmi generate-resume --jd-file path/to/jd.txt --dry-run

# Skip the web_search research step (uses a generic-but-personalised opener)
uv run jmi generate-resume --jd-file path/to/jd.txt --no-research

# Cap spend at $0.20 per generation
uv run jmi generate-resume --jd-file path/to/jd.txt --budget-usd 0.20
```

Typical cost: ~$0.17 per generation at list prices ($0.09 on a 7-day
research cache hit). Every generation persists into `tailored_resumes`
as an audit row. See
[ADR-0016](docs/adr/0016-resume-generator-and-research-agent.md) for the
ten architectural decisions behind it.

Run `uv run jmi --help` for the full command list and `uv run pytest` for the
backend test suite. The HITL Chrome extension lives in [`extension/`](extension/)
and is loaded unpacked into Chrome.

### Configuration

`.env` holds three settings that matter:

- `DATABASE_URL` — Postgres connection string; the template points at the local
  Docker instance and works out of the box.
- `ANTHROPIC_API_KEY` — required by `jmi extract`; the rest of the pipeline runs
  without it.
- `JMI_INGEST_TOKEN` — shared secret between the backend and the Chrome extension
  for the HITL ingest endpoint ([ADR-0009](docs/adr/0009-hitl-ingestion-pivot.md)).

## Project status

JMI is built in five phases. Phase 1 is essentially complete, Phase 2 shipped as a
proof of concept, and Phase 3 is in design.

| Phase | Scope | Status |
|---|---|---|
| **1 — Ingestion** | Three ToS-clean sources → Postgres → LLM extraction | ~95% complete |
| **2 — Analytics** | Embeddings, KMeans clustering, Markdown + HTML market report | PoC merged ([#20](https://github.com/MateuszJastrzebski21/job-market-intelligence/pull/20)) |
| **3 — RAG résumé generator** | Retrieval over a personal achievement corpus → tailored CV bullets and cover letters | PR-3.1 through PR-3.4 merged; PDF + eval framework pending |
| **4 — HITL apply agent** | Match scoring + form-fill, with a human approval gate on every submission | Planned |
| **5 — Production / MLOps** | Deployment, scheduled ingestion, monitoring, cost tracking | Planned |

Phase 1 delivers the full ingest → extract pipeline: three sources writing one
`JobPosting` table, and an LLM extractor producing validated `JobExtract` records
with prompt caching and token tracking. Phase 2's proof of concept added the first
downstream layer — embeddings, clustering, and a shareable market report — and its
choices are recorded in [ADR-0011](docs/adr/0011-phase2-poc-choices.md).

Phase 3 has shipped the resume generator end-to-end: achievement ingestion
(PR-3.1), custom RAG pipeline (PR-3.2), LangChain comparison (PR-3.3), and
the tailored resume + smart cover letter agent (PR-3.4 — see
[ADR-0016](docs/adr/0016-resume-generator-and-research-agent.md)). PDF
rendering and a resume-quality eval framework are the remaining pieces.
The full phase plan and timeline live in [`docs/roadmap.md`](docs/roadmap.md).

## Engineering discipline

This is a portfolio project, so the engineering process is part of the deliverable.

- **Architecture decisions are recorded.** 7 ADRs in [`docs/adr/`](docs/adr/)
  capture non-trivial choices before the code is written — what was decided, why,
  and what was rejected.

- **The codebase is reviewed.** An internal codebase review identified and closed
  6 fix-now items before Phase 3 work began. The findings are in
  [`docs/audit-2026-05-18.md`](docs/audit-2026-05-18.md); closure is verified in
  [`docs/verification-2026-05-18.md`](docs/verification-2026-05-18.md).

- **The architecture is built to extend.** Ingestion and extraction are separated
  stages, domain models are Pydantic, and persistence goes through a repository
  layer — so a new domain (Phase 3's achievement corpus) slots in without reworking
  the pipeline.

- **Behaviour is tested.** 117 pytest tests cover the Python backend and 89 vitest
  tests cover the Chrome extension; both suites run in CI.

- **Modern Python tooling is the baseline.** ruff (lint + format), mypy in strict
  mode, pre-commit hooks, and a GitHub Actions CI workflow that gates every pull
  request.

- **The roadmap is versioned.** [`docs/roadmap.md`](docs/roadmap.md) is updated by
  PR at every phase merge, giving the phase plan its own decision trail.

## Tech stack

| Area | Choices |
|---|---|
| **Language & tooling** | Python 3.12, uv, ruff, mypy (strict), pre-commit, GitHub Actions |
| **Data** | Postgres 15 + pgvector, SQLAlchemy 2.0, Alembic |
| **LLM & analytics** | Anthropic SDK (Claude Opus 4.7, prompt caching), sentence-transformers, scikit-learn |
| **API & CLI** | FastAPI (HITL ingest endpoint), Typer (`jmi` CLI), Pydantic v2, structlog |
| **Extension** | Chrome MV3 — background service worker, offscreen DOM parsing, popup + options |

Sync-first by default; async is introduced only on a measured bottleneck.

## License

Released under the [MIT License](LICENSE).

JMI is a personal portfolio project built by one developer. It is shared publicly
as a record of the engineering process — the ADRs, the audit trail, and the
roadmap — rather than as a tool seeking external contributors.
