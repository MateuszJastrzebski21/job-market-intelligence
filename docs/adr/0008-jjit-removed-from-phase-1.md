# ADR-0008: JJIT Removed from Phase 1

**Status:** Accepted
**Date:** 2026-05-14
**Context of:** Week 2 plan-mode session for the JustJoinIT scraper (`docs/_archived/jjit-plan-abandoned.md`)

## Context

The Week 1 portal-order plan (CLAUDE.md) put JustJoinIT in Week 2. During the Week 2 planning session we ran ToS / robots.txt diligence on JJIT before writing any code, and surfaced two operator signals:

1. **`https://justjoin.it/robots.txt`** declares:

   ```
   User-agent: *
   Disallow: /api/
   ```

   The endpoints we'd scrape (`/api/candidate-api/offers` and `/api/candidate-api/offers/{slug}`) fall under this disallow.

2. **JJIT regulamin point 11.3** (Polish ToS, browser-readable from the footer of `https://justjoin.it/`) explicitly prohibits "automatyczne pobieranie ... danych zawartych w Serwisie" without the operator's express written consent. The clause covers any actor and references civil and criminal liability, including the Polish 2001 Database Protection Act (ustawa o ochronie baz danych z 2001 r.) per regulamin point 1.2.

Combined, these two signals are unambiguous. robots.txt alone is advisory; an explicit ToS prohibition with statutory backing is binding.

## Decision

JustJoinIT scraping is **not implemented in Phase 1**. The Week 2 slot is given to NoFluffJobs, promoted from Week 3. Phase 1 portal order (updated in CLAUDE.md in the same PR as this ADR):

| Week | Source | Status |
|---|---|---|
| 1 | Hugging Face Jobs | done |
| 2 | NoFluffJobs | promoted from Week 3 |
| 3 | Wellfound or YC Work at a Startup | unchanged criteria; pick in Week 2 retro |
| 4 | the other of Wellfound / YC, or Bulldogjob | unchanged |
| — | JustJoinIT | excluded by this ADR |
| — | LinkedIn | excluded (ToS + anti-bot, prior decision) |
| — | Otta | excluded (junior roles rare, prior decision) |

## Consequences

**Positive**

- Removes legal exposure from the 2001 Polish Database Protection Act and the regulamin's stated civil/criminal liability path.
- Honors the operator's `robots.txt` signal.
- ~80% of the JJIT plan content (Alembic-first migration, separated three-step `scrape` → `fetch-details` → `extract` pipeline, multi-company mapper, Quill-aware HTML parser, Option-A "structured data lives in `raw_payload`" treatment) ports to NoFluffJobs with portal-specific changes only. Saved as `docs/_archived/jjit-plan-abandoned.md` for reuse in the NFJ planning session.

**Negative**

- The Polish IT job-market signal we expected from JJIT is partly lost. NoFluffJobs covers Polish IT with broad overlap; missing the JJIT-specific listings is the cost.
- Loses the planned dedup test ("scrape NFJ + JJIT, count overlap"). Defer to Phase 2 if a second Polish source becomes viable.

**Neutral**

- Phase 1 still ships four portals; the technical patterns (Alembic, separated pipeline if needed, multi-source CLI dispatch, repository extensions) all still get built — they're now built against NFJ instead of JJIT.

## Alternatives Considered

### (b) Ignore robots.txt + interpret regulamin 11.3 liberally

- **Plus:** keeps the original portal plan, accesses the actual job-hunt target portal, faster to ship.
- **Minus (decisive):** regulamin 11.3 is not silent or ambiguous — it explicitly prohibits automated extraction by any actor without written consent. "Liberal interpretation" reduces to "operator said no, we proceeded anyway." The civil/criminal liability language combined with the 2001 ustawa o ochronie baz danych reference makes this a non-trivial legal exposure for a portfolio project, even at <200 req/day.
- **When this would make sense:** never for an unauthenticated scrape against a Polish operator's published ToS prohibition. Possibly relevant if we later obtain written consent.

### (c) Contact JJIT and request written consent / partner API

- **Plus:** would unblock the original plan with full legitimacy.
- **Minus:** unknown response time, response likely "no" for a personal-use research bot, blocks Week 2 indefinitely.
- **When this would make sense:** Phase 5+ if the project becomes a real product with a value proposition for JJIT (e.g., aggregated salary insights co-branded).

### (a) Drop JJIT entirely without pivot

- **Plus:** simplest.
- **Minus:** loses the Week 2 milestone. CLAUDE.md already prioritized "second source by Week 2."
- **Why we picked the pivot instead:** NFJ was already on the Phase 1 roadmap (Week 3); promoting it to Week 2 is a one-line schedule change, not a strategic pivot.

## Consequences for Code Today

- No code changes from this ADR. Schema, repositories, scrapers, extractor, and CLI all unchanged.
- The Week 2 implementation work (Alembic adoption, source-dispatch refactor in `cli.py`, possibly nullable description columns) shifts target from JJIT to NFJ. Re-evaluate the separated-pipeline necessity in the NFJ plan-mode session — the structural choice depends on NFJ's own list-vs-detail API shape, not JJIT's.
- `src/jmi/sources/wellfound/` directory stub is untouched (off-topic for this ADR).

## References

- [`docs/_archived/jjit-plan-abandoned.md`](../_archived/jjit-plan-abandoned.md) — full Week 2 plan-mode session output, preserved as engineering artifact for NFJ reuse.
- [`CLAUDE.md`](../../CLAUDE.md) — "Phase 1 portal order" section updated in the same PR as this ADR.
- [ADR-0006](0006-extraction-pipeline-architecture.md) — separated pipeline; still applies to NFJ.
- `https://justjoin.it/robots.txt` — operator signal.
- JJIT regulamin (browser-readable from the footer of `https://justjoin.it/`), point 11.3 (data extraction prohibition) and point 1.2 (reference to the 2001 ustawa o ochronie baz danych).
