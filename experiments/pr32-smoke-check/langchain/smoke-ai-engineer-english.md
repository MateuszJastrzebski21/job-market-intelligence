# Smoke check (LangChain): AI Engineer (English)

**Pipeline:** `jmi.rag_langchain.pipeline.RagPipeline` (PR-3.2 Worktree B)
**Language:** en
**K:** 5
**Rerank:** on (CrossEncoderReranker with bge-reranker-base)

## Input JD

```
We are hiring an AI Engineer to build LLM-powered features in a Python codebase. The role owns prompt engineering, retrieval pipelines, and evaluation infrastructure. You should be comfortable with embeddings, vector stores (pgvector or similar), retrieval-augmented generation, and integrating Anthropic/OpenAI APIs end-to-end. Bonus: experience with agentic workflows, observability for LLM systems (token + cost tracking), and shipping ML-touching code to production with tests + CI.
```

## Retrieved Chunks (top-5)

### 1. score=0.702  section=context  chunk_id=job-market-intelligence-jmi-ai-engineer-portfolio-flagship::context

achievement_id: `02067d32-9267-408d-8a01-0e9aa41707af`  chunk_index: 0

```
[Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Context]

Job Market Intelligence (JMI) is my flagship portfolio project: a
Polish AI/ML job-market pipeline that ingests job postings, extracts
structured data with an LLM, stores everything in Postgres with
pgvector, and runs analytics and (in progress) retrieval-augmented
résumé generation on top. It's the centerpiece of my AI Engineer
job applications and the project I point hiring managers at when
they ask "what's your most ambitious recent build."
```

### 2. score=0.722  section=impact  chunk_id=job-market-intelligence-jmi-ai-engineer-portfolio-flagship::impact

achievement_id: `02067d32-9267-408d-8a01-0e9aa41707af`  chunk_index: 2

```
[Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Impact]

Concrete state of the project at the time of writing:

- Phase 1 ingestion functional across three sources (HF Jobs API,
  JJIT via extension, NoFluffJobs via extension).
- Phase 2 analytics PoC merged.
- Phase 3 PR-3.1 (data layer for personal-corpus RAG) merged on main.
- Quality bar held: pytest 161 passing, mypy strict 0 errors across
  52 source files, ruff clean, pre-commit 8 hooks passing on every
  commit.
- A dedicated research dossier (5,046 words) drafted for PR-3.2 to
  compare custom RAG against LangChain on this corpus shape, with
  retrieval metrics (recall@k, MRR, nDCG) reported with bootstrap
  confidence intervals.

The project is the most concrete evidence I have that I can build
and operate a typed Python system with senior-level discipline —
ADR-backed decisions, mypy strict, security constraints baked into
the schema, idempotent ingest, all of it.
```

### 3. score=0.705  section=approach  chunk_id=job-market-intelligence-jmi-ai-engineer-portfolio-flagship::approach

achievement_id: `02067d32-9267-408d-8a01-0e9aa41707af`  chunk_index: 1

```
[Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Approach]

JMI is structured as five phases with explicit deliverables per
phase. Phase 1 is terms-of-service-clean ingestion: a server-side
scraper for Hugging Face Jobs (whose API permits it) plus a
human-in-the-loop Chrome extension (Manifest V3) for portals whose
terms forbid server-side scraping — JJIT and NoFluffJobs are
collected via the operator's own browser, with the page DOM
captured locally rather than fetched server-side. This design
choice is recorded in ADR-0008 and is one of the project's sharper
constraints.

Phase 2 is an analytics proof of concept: sentence-transformer
embeddings (all-MiniLM-L6-v2, 384-dim), KMeans clustering, and a
generated Markdown + HTML market report. PoC merged as PR #20.

Phase 3 is a custom RAG résumé generator. PR-3.1 — already merged
— adds the Achievement domain (Pydantic model with a path-traversal
sandbox per the H1 security constraint, ORM with separate
purgeable `achievements` and `achievement_embeddings` tables, an
Obsidian-markdown ingestor, and a CLI command). PR-3.2 (in progress)
implements retrieval. The plan compares a custom RAG implementation
to a LangChain reimplementation as an ADR-backed engineering
exercise.

Every non-trivial decision is captured in an Architecture Decision
Record. ADRs 0005 (Pydantic structured output), 0006 (separated
ingestion/extraction pipeline), 0008 (ToS-clean HITL), 0011 (Phase 2
PoC choices), 0012 (repository pattern with inline Protocols), 0013
(future-import + UP037 atomic-commit gotcha), and 0014 (Achievement
domain schema) are the project's durable design memory.
```

### 4. score=0.666  section=lessons  chunk_id=job-market-intelligence-jmi-ai-engineer-portfolio-flagship::lessons

achievement_id: `02067d32-9267-408d-8a01-0e9aa41707af`  chunk_index: 3

```
[Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Lessons]

The single most valuable lesson is plan-mode discipline. Every
non-trivial change in JMI gets a plan-mode review before any code
is written — design alternatives compared, security constraints
checked, scope edges identified. Plan-mode caught architectural
errors that would have shipped as bugs in a "just start coding"
workflow, and it doesn't slow the project down; it speeds it up
because rework is the most expensive thing in a long-running
codebase.

A second lesson: a privacy audit isn't paranoia, it's evidence-based
caution. Three separate leaks of my real career data into the
public repo were caught and fixed during Phase 3 development — in
sample files, in roadmap planning notes, and in test fixtures —
each missed during the prior cleanup. The lesson now baked into the
project's pre-merge checklist: any change touching example data,
test fixtures, or roadmap content must grep the whole repo for
personal-data keywords before pushing.
```

### 5. score=0.671  section=approach  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::approach

achievement_id: `3052f2f4-050d-429e-b667-5016aef376ed`  chunk_index: 1

```
[Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Approach]

The dataset is 3+ years of BTC OHLCV data pulled from the Binance
API. Feature engineering produces 30+ technical indicators (momentum,
volatility, volume-derived, trend-following) as model inputs, with
the target being a binary directional label on the next period.

The validation discipline is walk-forward: the time-series is sliced
into expanding (or rolling) train windows with sequential
out-of-sample evaluation, so the model is never evaluated on data
that overlaps with its training in calendar time — the standard
correct setup for any market-data ML problem and the one that
distinguishes a credible thesis from a leak-prone notebook.

The two model families under comparison are XGBoost and LightGBM,
chosen for their strong tabular-data performance and for the fact
that comparing them on this dataset is itself part of the thesis
contribution.
```


## Generated Bullets

- Build LLM-powered features in a typed Python codebase, ingesting job postings and extracting structured data with an LLM into Postgres with pgvector — held to pytest 161 passing, mypy strict 0 errors across 52 source files, and ruff clean on every commit — [Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Impact]
- Design retrieval-augmented generation pipelines end-to-end, including a custom RAG résumé generator with a dedicated Achievement domain (Pydantic model, ORM with separate `achievements` and `achievement_embeddings` tables, Obsidian-markdown ingestor, and CLI) — [Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Approach]
- Build evaluation infrastructure for retrieval, reporting recall@k, MRR, and nDCG with bootstrap confidence intervals, captured in a 5,046-word research dossier comparing custom RAG against a LangChain reimplementation — [Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Impact]
- Implement embeddings and vector-store workflows using sentence-transformer embeddings (all-MiniLM-L6-v2, 384-dim) and pgvector, alongside KMeans clustering and a generated Markdown + HTML analytics report — [Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Approach]
- Ship ML-touching code to production discipline with ADR-backed decisions, pre-commit 8 hooks, and a plan-mode review before any non-trivial change — a workflow that catches architectural errors before they ship as bugs — [Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Lessons]

## Notes

_Operator labels:_ grounded / partial / hallucinated

- bullet 1:
- bullet 2:
- bullet 3:
- bullet 4:
- bullet 5:

_Side-by-side comparison with Worktree A's `experiments/pr32-smoke-check/ai-engineer-english.md`:_
