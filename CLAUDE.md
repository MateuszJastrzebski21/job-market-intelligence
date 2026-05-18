# CLAUDE.md — JMI

Job Market Intelligence — a Polish AI/ML job-market pipeline: ingest job postings
(API scrape + HITL Chrome-extension) → LLM extract → Postgres → analytics. Portfolio
flagship for AI Engineer applications, and a working personal tool.

## Current state (2026-05-18)

- **Phase 1 — ~95% done.** ToS-clean ingestion across three sources: Hugging Face
  Jobs (API scraper) plus JustJoinIT and NoFluffJobs (HITL Chrome-extension).
- **Phase 2 — PoC merged (PR #20).** Analytics PoC: embeddings + KMeans clustering +
  Markdown/HTML market report via `jmi analyze`. See ADR-0011.
- **Phase 3 — next.** RAG résumé generator — the largest and highest-payoff phase.
- Phases 4–5 (HITL apply agent; production / MLOps) are planned. Full plan and
  timeline live in `docs/roadmap.md`.

## Stack

- Python 3.12, `uv` for package management.
- Postgres 15 + pgvector — a single DB for data and embeddings.
- Docker Compose for local Postgres.
- Typer for the `jmi` CLI.
- FastAPI — in Phase 1 since Week 2 for the HITL ingest endpoint (ADR-0009);
  dashboard endpoints remain Phase 2.
- Sync first; async only on a measured bottleneck.

## Ingestion sources & ToS posture

The Polish job portals (JustJoinIT, NoFluffJobs) prohibit automated server-side
extraction in their ToS, backed by the 2001 PL Database Protection Act. JMI therefore
ingests them **human-in-the-loop**: a Chrome extension captures user-selected postings
in the user's own browser session and POSTs them to the local FastAPI ingest endpoint.
The JMI backend never scrapes those portals server-side. See ADR-0009.

- **Hugging Face Jobs** — API scraper (`jmi scrape -s huggingface`); ToS-clean, the
  template for any future API-clean source.
- **JustJoinIT** — HITL Chrome-extension ingestion (ADR-0009). Server-side *scraping*
  of JJIT stays excluded (ADR-0008); the extension is the sanctioned path, and `jjit`
  is an active `Source`.
- **NoFluffJobs** — HITL Chrome-extension ingestion (ADR-0009).
- LinkedIn / Otta — out of scope (ToS + anti-bot; sparse junior-role volume).

Every source writes one `JobPosting` table and feeds the same downstream `jmi extract`
pipeline — the separated pipeline of ADR-0006.

## Where things are

- `src/jmi/` — backend: `sources/` (scrapers), `api/` (FastAPI ingest), `extractors/`
  (LLM extraction), `analytics/` (Phase 2), `evaluation/`, `storage/`, `db/`.
- `extension/` — Chrome MV3 extension (HITL ingestion).
- `docs/adr/` — architecture decision records. `docs/roadmap.md` — the phase plan.
- Architecture decisions are recorded as ADRs before non-trivial changes.
