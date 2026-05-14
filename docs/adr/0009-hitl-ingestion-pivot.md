# ADR-0009: HITL Ingestion Pivot — Chrome Extension + FastAPI

**Status:** Accepted
**Date:** 2026-05-15
**Context of:** Week 2 pivot following ADR-0008 (JJIT excluded) and the NoFluffJobs ToS-diligence research carried out 2026-05-14/15. Implementation roadmap lives in [`docs/extension-plan.md`](../extension-plan.md).

## Context

[ADR-0008](0008-jjit-removed-from-phase-1.md) excluded JustJoinIT from Phase 1 on the basis of regulamin point 11.3 (explicit prohibition of automated data extraction) and `robots.txt: Disallow: /api/`. NoFluffJobs was promoted from Week 3 to Week 2 as the replacement Polish-market source.

ToS diligence on NoFluffJobs (carried out 2026-05-14/15 ahead of any code) surfaced an equivalent prohibition. NFJ regulamin § 2 ust. 9 states "Zakazane jest powtarzające się lub systematyczne pobieranie ... danych zawartych w Serwisie." § 21 ust. 4 reinforces this with a downloading restriction. § 1 ust. 7 references the Polish 2001 Database Protection Act (ustawa o ochronie baz danych z dnia 27 lipca 2001 r.) as the statutory backing — the same sui generis database-right framework cited by JJIT regulamin point 1.2.

**Pattern recognition:** two consecutive Polish tech job portals (JJIT, NFJ) explicitly prohibit automated/systematic extraction at the ToS level, both backed by the 2001 Database Protection Act. Continuing one-portal-research-then-pivot through Week 3 (Wellfound? YC?) and Week 4 would compound the cost — every week we'd spend research effort to find another "no." The Polish tech job market does not provide a server-side scraping path at acceptable legal risk.

**Pivot motivation:** instead of abandoning Polish-market coverage (which is the actual job-hunt target — see Alternative (a) below), shift the *ingestion mechanism* to one that doesn't trigger the ToS prohibition. The established legal pattern for this is the **webclipper**: Pocket, Notion Web Clipper, Instapaper. Each runs as a browser extension in the user's own session, fetching only what the user has explicitly chosen to save. The data flow is one-directional from the operator's site → user's browser → user's downstream storage, with user agency at the center of every action.

The two-portal precedent (JJIT 11.3 + NFJ § 2 ust. 9) is sufficient to justify a systemic pivot rather than a third per-portal investigation.

## Decision

Adopt **Human-in-the-Loop (HITL) ingestion** as the primary path for ToS-restricted job portals in Phase 1:

1. A Chrome Manifest V3 extension provides the UI surface. The user navigates to a listing page they want to save, scrolls through the cards they want captured, and clicks "Save jobs on this page" in the extension popup. No background automation — every save is user-initiated.
2. A new FastAPI service on `http://127.0.0.1:8000` exposes `POST /api/ingest`, `POST /api/details`, and `GET /api/health`. The extension POSTs partial postings (URL + listing-page metadata) on save, then POSTs filled postings after its background service worker fetches the detail pages.
3. **Background detail fetch happens in the extension's service worker** — i.e. in the user's browser, in the user's session. The JMI backend never makes outbound HTTP requests to job portals. Data flow is one-directional: portal → user's browser → JMI backend.
4. Background fetches are limited to URLs the user just clicked save on — never speculative, never paginated by the extension, never recurring on a timer.
5. **FastAPI is promoted from Phase 2 (Week 5+) to Phase 1 (Week 2)** to host the ingest endpoint. Dashboard endpoints remain in Phase 2 as planned.
6. The 8-PR implementation roadmap is documented in [`docs/extension-plan.md`](../extension-plan.md); this ADR is PR1 of that sequence.

The existing Hugging Face API scraper (`jmi scrape -s huggingface`) continues unchanged — HF Jobs is ToS-clean for API access and remains the API-scraper template. The ingest endpoint and the CLI scraper coexist; both write `JobPosting` rows that the existing `jmi extract` pipeline processes identically (ADR-0006 separated pipeline preserved).

## Consequences

**Positive**

- ToS-clean coverage of JJIT and NFJ (and any future Polish portal) via the established webclipper pattern. No statutory exposure to the 2001 Database Protection Act for either operator.
- Established legal precedent (Pocket / Notion Web Clipper / Instapaper) makes the architecture defensible by analogy rather than novel interpretation.
- FastAPI now lands in Phase 1 — REST API surface available three weeks earlier than originally planned. Dashboard prototyping can begin sooner if needed.
- The extension codebase becomes a portfolio-worthy artifact (browser-tooling skill demonstration on top of the data pipeline).

**Negative**

- ~3000 LoC of additional implementation work across 8 PRs (≈2 weeks of evening sessions). See PR sequence in `docs/extension-plan.md` §9.
- Project now has two languages: Python (backend) and JavaScript (extension content scripts + service worker). Adds a build/test toolchain on the JS side (vitest + jsdom).
- MV3 service-worker constraints: no `DOMParser` available in workers, requiring an offscreen-document context for HTML parsing (well-documented but non-trivial).
- User friction: manually browsing + scrolling + clicking save replaces what could have been a fully automated daily cron. Acceptable trade against the legal risk.

**Neutral**

- Same downstream pipeline (`jmi extract`, embeddings in Phase 2, RAG in Phase 3) — source-agnostic by design.
- Hugging Face scraper unchanged (Phase 1 Week 1 work preserved). The HITL path and the API path coexist; new ToS-clean portals can still land as API scrapers under `src/jmi/sources/`.
- Schema impact is small: `description_html` and `description_text` become nullable (PR2 Alembic migration); `Source` literal widens to include `jjit`, `nofluff`, `linkedin`.

## Alternatives Considered

### (a) Abandon Polish portals, pivot to US/global sources only

- **Plus:** simplest architecture, no extension required, sticks to API-scraper template from Week 1.
- **Minus (decisive):** NFJ and JJIT cover the actual job hunt — the user is a Polish junior developer targeting AI Engineer roles primarily in the PL market. JMI without Polish coverage becomes a portfolio piece divorced from real use. The point of the project is to answer "what's hiring in my market?" not "what's hiring on YC."
- **When this would make sense:** if the user shifts target geography to a market with API-friendly portals (US: HF Jobs already covers; perhaps Wellfound, YC, RemoteOK).

### (b) Request written consent from each portal operator

- **Plus:** would unblock the original server-side scraping plan with full legitimacy.
- **Minus (decisive):** unknown response time (weeks to months), response is likely "no" for a personal-use research bot with no commercial proposition to the operator, blocks Weeks 2–N indefinitely. Two simultaneous "we're waiting on legal" tracks across JJIT and NFJ is operationally untenable.
- **When this would make sense:** Phase 5+ if the project becomes a real product with a value proposition for the operator (e.g. aggregated market insights co-branded back to the portal).

### (c) Manual CSV upload UI

- **Plus:** trivial to implement — a single `POST /api/upload` endpoint accepting CSV with the existing `JobPosting` columns.
- **Minus (decisive):** defeats the data-pipeline purpose. The user would need to extract title / salary / tech stack / location for every posting by hand, copying from the portal into a spreadsheet — moving the work from system to human. The Phase 3 RAG-from-real-data value depends on structured ingestion at scale, not on human-curated rows.
- **When this would make sense:** never as the primary path; possibly as a maintenance escape hatch in Phase 5+ if a portal becomes unreachable via extension.

### (d) Private/local scraping with a public empty portfolio

- **Plus:** covers the Polish market for the user's actual use, keeps the architecture simple.
- **Minus (decisive):** consistency-with-self problem. ADR-0008 is public and states "JJIT excluded for ToS reasons." Operating a private scraper against the same portal contradicts the documented stance. Character cost (the project is also a professional artifact — coherence matters) plus interview risk if discovered. Discussed at length 2026-05-14 in the pivot conversation.
- **When this would make sense:** never — the consistency cost is binding regardless of detection probability.

## Consequences for Code Today

- **No code changes from this ADR.** This is PR1 of the 8-PR roadmap in `docs/extension-plan.md`; PR1 is docs only.
- PR2 (Alembic adoption) follows: schema becomes nullable on `description_html` / `description_text` via the first non-baseline migration. Pre-flight `pg_dump` backup is part of the PR2 verification checklist.
- PR3 (FastAPI ingest) introduces `src/jmi/api/`, `POST /api/ingest`, `POST /api/details`, `GET /api/health`, plus `JobPostingRepository.update_description()` and `list_pending_details()`.
- PR4–7 (extension) land as a new top-level `extension/` directory at the repo root (MV3 manifest, popup, options, content scripts per portal, background service worker with rate-limited queue).
- CLAUDE.md is updated in this PR to reflect FastAPI's Phase-1 status (one-line change).
- The HF API scraper (`src/jmi/sources/huggingface/`) is untouched and remains the template for any future API-clean portal.

## References

- [ADR-0006: Extraction Pipeline Architecture](0006-extraction-pipeline-architecture.md) — separated pipeline; the ingest endpoint occupies the "scrape" phase and `jmi extract` remains the "extract" phase.
- [ADR-0008: JJIT Removed from Phase 1](0008-jjit-removed-from-phase-1.md) — precedent for the Polish-market ToS pattern; contains the verbatim JJIT regulamin 11.3 quote.
- [`docs/extension-plan.md`](../extension-plan.md) — authoritative implementation roadmap (8 PRs, architecture diagram, CORS, rate limiting, error handling, end-to-end verification).
- NoFluffJobs regulamin (browser-readable from the footer of `https://nofluffjobs.com/`): § 1 ust. 7 (references the 2001 Database Protection Act), § 2 ust. 8–9 (prohibits repeated or systematic extraction of postings), § 21 ust. 4 (downloading restriction).
- Ustawa z dnia 27 lipca 2001 r. o ochronie baz danych (Polish 2001 Database Protection Act) — the statutory backing common to both JJIT and NFJ regulaminy.
- Webclipper precedent (industry-customary pattern, not case law): Pocket, Notion Web Clipper, Instapaper — browser extensions that fetch user-selected pages in the user's session for personal archiving.
