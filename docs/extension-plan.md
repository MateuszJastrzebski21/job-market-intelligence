# JMI HITL Ingestion — Extension Plan (Phase 2 → Phase 1 promotion)

## Context

ADR-0008 merged: JustJoinIT excluded from Phase 1 (regulamin point 11.3 + robots.txt `Disallow: /api/`).

Today's NoFluffJobs research surfaced regulamin § 2 ust. 9 also prohibiting "powtarzające się lub systematyczne pobieranie poszczególnych ogłoszeń" (repeated or systematic extraction of individual postings). Pattern: the Polish tech job market broadly bans server-side scraping at the ToS level. Continuing one-portal-at-a-time research-then-pivot would cost a week per portal.

Pivot: Human-in-the-Loop ingestion via Chrome MV3 extension. User-initiated save action per listing page → extension parses visible job cards → JMI backend (FastAPI on localhost) stores partial postings → extension's background service worker fetches detail pages (in user's browser context) → updates JMI. Established legal precedent: Pocket, Notion Web Clipper, Instapaper — webclipper pattern with user agency at the core.

This promotes FastAPI from Phase 2 (Week 5+) into Phase 1 immediately.

## Goals & non-goals

**Goals**
- ToS-clean ingestion path for JJIT, NFJ (LinkedIn deferred to second wave).
- Reuse existing JMI architecture: ADR-0006 separated pipeline preserved (ingest endpoint = scrape phase, existing `jmi extract` = extract phase).
- Coexist with HF API scraper (`jmi scrape -s huggingface` unchanged, HF Jobs is ToS-clean).
- 8 small PRs, each ≤600 LoC, reviewable in ≤30 min.
- Developer-mode unpacked load only (no Chrome Web Store).

**Non-goals**
- Auto-pagination from extension (user navigates pages manually; one click = one page).
- Cron / polling / scheduled fetches.
- Server-side fetching of any URL the user hasn't seen (HITL invariant).
- Migration of HF scraper to extension path (HF stays as the API scraper).
- Public extension distribution.

## 1. Architecture overview

```
+--------------------------+              +-----------------------+
|    Browser (User)        |              |  JMI Backend (local)  |
|                          |              |                       |
|  Listing page (JJIT/NFJ) |              |  FastAPI :8000        |
|  +-------------------+   |              |  (binds 127.0.0.1)    |
|  | content script    |   |              |                       |
|  | (parses cards on  |   |              |  POST /api/ingest     |
|  | popup request)    |   |              |    (partial postings) |
|  +---------+---------+   |    POST      |                       |
|            |             +-------------> POST /api/details      |
|            v             |    POST      |    (filled postings)  |
|  +-------------------+   +-------------> GET  /api/health       |
|  | service worker    |   |              |                       |
|  | (orchestrator +   |   |              |  Storage:             |
|  | rate-limited      |   |              |   JobPostingRepository|
|  | detail fetcher)   |<--+              |    + new methods:     |
|  +---------+---------+   | fetch detail |    update_description |
|            |             | URLs (in     |    list_pending_      |
|            v             | user's       |      details          |
|  +-------------------+   | session,     |                       |
|  | offscreen document|   | one-shot)    |                       |
|  | (DOMParser for    |   |              |                       |
|  | fetched HTML)     |   |              |                       |
|  +-------------------+   |              |                       |
+--------------------------+              +----------+------------+
                                                     |
                                                     v
                                          +----------+------------+
                                          | jmi extract -n N      |
                                          | (existing, unchanged) |
                                          +-----------------------+
```

### HITL invariants (legal stance — load-bearing)

1. **Every save action is user-initiated**: clicking the "Save jobs on this page" button in the extension popup, on a tab the user opened themselves.
2. **Background detail fetch happens in the extension's service worker** — i.e. in the user's browser, in the user's session. JMI backend never makes outbound HTTP requests to job portals. Data flow is one-directional: portal → user's browser → JMI backend.
3. **Background fetches are limited to URLs the user just clicked save on** — never speculative, never paginated by the extension, never recurring on a timer.
4. **Rate limits are intentionally polite** even though the legal premise allows browser-rate access (§5).

### Coexistence with existing pipeline (ADR-0006)
- `jmi scrape -s huggingface` unchanged — HF API is ToS-clean.
- `jmi extract` unchanged — operates on `JobPosting` rows regardless of how they got there (CLI scrape vs HTTP ingest).
- New ingest endpoints write the same `JobPosting` rows. After ingest + detail fetch, a JJIT/NFJ row looks indistinguishable from an HF row to the extractor.

## 2. Per-PR breakdown

8 PRs in main sequence; PR8 deferred to second wave.

### PR1 — `docs: ADR-0009 HITL ingestion pivot`

Pure docs. Lays the legal/architectural rationale **before** any code is reviewed (ADR convention from ADR-0006/0008).

Files:
- `docs/adr/0009-hitl-ingestion-pivot.md` (new, matches ADR-0006/0008 template: Status / Date / Context / Decision / Consequences ± / Alternatives Considered / Consequences for Code Today / References)
- `CLAUDE.md` — update line "FastAPI added in Phase 2 (Week 5+)" → "FastAPI: in Phase 1 since Week 2 for the ingest endpoint (ADR-0009)"

ADR-0009 contents:
- Context: ADR-0008 → today's NFJ regulamin § 2 ust. 9 finding → pattern across Polish tech portals
- Decision: HITL via MV3 extension + FastAPI ingest endpoint on localhost
- Consequences ± (FastAPI promoted, new extension subdir, schema becomes nullable on description_*, legal stance documented)
- Alternatives considered: (a) abandon Polish portals (rejected: NFJ + JJIT cover the actual job hunt); (b) request written consent from each portal (rejected: blocks roadmap indefinitely); (c) manual CSV upload UI (rejected: defeats the data-pipeline purpose)
- Verbatim regulamin quotes: JJIT 11.3 (already in ADR-0008) + NFJ § 2 ust. 9 — each ≤14 words, in quotation marks
- Webclipper precedent reasoning: Pocket / Notion Web Clipper / Instapaper as established legal pattern; references to relevant case law if the user has any (otherwise the precedent is industry custom)
- Reference to `docs/extension-plan.md` (this plan) for the implementation roadmap

LoC est: 250.

### PR2 — `feat: Alembic adoption + nullable description columns`

Foundation for all future schema changes. Pure infra; splits cleanly from PR3.

Contents:
- `uv add alembic`
- `alembic init src/jmi/db/migrations` (src-layout — keeps migrations in the installed package)
- `env.py` configured to import `Base` from `jmi.db.base` and read `DATABASE_URL` from `jmi.config.get_settings()`
- Migration 0001 — baseline. Generated via `alembic revision --autogenerate -m "baseline"`. Should match current `Base.metadata` exactly. On the live dev DB run `alembic stamp head` (don't re-execute DDL — tables already exist; we just want Alembic's bookkeeping table primed).
- Migration 0002 — `description_html`, `description_text` → nullable. (`ALTER COLUMN ... DROP NOT NULL`.)
- `cli.py` `init-db` command refactored to call `command.upgrade(cfg, "head")`.
- Pydantic models updated: `description_html: str | None`, `description_text: str | None` in `src/jmi/models/job.py`. Mirror in ORM (`src/jmi/db/models.py:28-29`). Update `_posting_to_orm` / `_posting_to_domain` mappers in `src/jmi/storage/jobs.py:89-120`.

Verification:
- **Pre-flight backup**: `docker compose exec postgres pg_dump -U postgres jmi > backup-before-alembic.sql`. Captures current state before any migration runs. Insurance against schema mishap during Alembic adoption; keep the file out of the worktree (add to `.gitignore` or store under `~/jmi-backups/`).
- `alembic upgrade head` from clean state matches existing schema.
- After PR2 merge, dev DB still has Week 1 HF data + extracts intact (cross-check vs the pg_dump file row counts).
- Run `alembic upgrade --sql` dry-run before committing 0001 — eyeball the SQL to confirm `UniqueConstraint(source, source_job_id)` and `JSONB` type are reproduced correctly (autogenerate sometimes misses these).

LoC est: 200.

### PR3 — `feat: FastAPI ingest endpoint`

First user-facing code change. New API surface, no UI yet.

Files added:
- `src/jmi/api/__init__.py`
- `src/jmi/api/app.py` — FastAPI app factory, CORS middleware, auth dependency
- `src/jmi/api/routes/ingest.py` — `POST /api/ingest`
- `src/jmi/api/routes/details.py` — `POST /api/details`
- `src/jmi/api/routes/health.py` — `GET /api/health`
- `src/jmi/api/schemas.py` — Pydantic request/response shapes
- `src/jmi/api/auth.py` — `verify_ingest_token` dependency

Files changed:
- `pyproject.toml` — `uv add fastapi "uvicorn[standard]"`
- `src/jmi/cli.py` — new `jmi serve` command → `uvicorn jmi.api.app:app --host 127.0.0.1 --port 8000`. Replaces hardcoded if/elif scrape dispatch with a small dict (`{"huggingface": HuggingFaceScraper}`); JJIT/NFJ never enter the CLI scrape path because they go through the extension.
- `src/jmi/models/job.py:9` — `Source = Literal["huggingface", "wellfound", "jjit", "nofluff", "linkedin"]`
- `src/jmi/storage/jobs.py` — add `update_description(id, html, text, raw_payload)`, `list_pending_details(source, limit)`. `get_by_source` already exists.
- `src/jmi/extractors/anthropic.py` — one-line skip guard: skip postings with empty/None `description_text`, log `extract.skip.no_description`. Carried over from the deferred JJIT plan.
- `src/jmi/config.py` — add `ingest_token: str | None` setting (read from env `JMI_INGEST_TOKEN`).
- `.env.example` — document `JMI_INGEST_TOKEN`.

Endpoint contracts:

`POST /api/ingest` — body:
```json
{
  "source": "jjit",
  "postings": [
    {
      "source_id": "<unique key from listing card>",
      "url": "https://justjoin.it/job-offer/...",
      "title": "Python Developer",
      "company_name": "Acme",
      "location_raw": "Warsaw, Hybrid",
      "salary_raw": "16000-24000 PLN",
      "posted_at": "2026-05-13T00:00:00Z",
      "raw_payload": { "<whole listing-card data>": "..." }
    }
  ]
}
```
Response: `{accepted: int, skipped_existing: int, invalid: [{idx, error}]}`.

Behavior:
- For each posting, mapper produces `JobPosting` with `description_html=None`, `description_text=None`, `scraped_at=now()`.
- Idempotency: `repo.get_by_source(source, source_id)` skip-if-exists.
- 401 if `X-Ingest-Token` header missing or doesn't match `JMI_INGEST_TOKEN`.
- 422 if body validation fails. Per-posting validation errors don't fail the whole batch — they're returned in `invalid` with idx.

`POST /api/details` — body:
```json
{
  "source": "jjit",
  "details": [
    {
      "source_id": "<same as in ingest>",
      "description_html": "<full body HTML>",
      "description_text": "<plain text via portal-specific parser>",
      "raw_payload_patch": { "detail": { "...additional fields..." } }
    }
  ]
}
```
Response: `{updated: int, skipped_unknown: int, invalid: [...]}`.

Behavior:
- For each detail, look up `JobPosting` by (source, source_id). If not found, count as `skipped_unknown` (extension shouldn't POST detail for posting we don't have, but we're defensive).
- Update in place via `repo.update_description(...)`. `raw_payload` is merged: existing + `{"detail": detail_dict}`.
- Token + 422 same as ingest.

`GET /api/health` — response: `{status: "ok", db_ok: bool, version: "0.1"}`. No auth required (popup polls this on open). DB check is a single `SELECT 1`.

CORS (per §4): allow_origins `["chrome-extension://*"]`, allow_headers includes `X-Ingest-Token`.

Tests (`tests/api/`):
- `test_ingest.py` — happy path, dedup skip, validation error, missing token rejected
- `test_details.py` — happy path, unknown source_id, schema mismatch
- `test_health.py` — db_ok true/false (mock session.execute to raise)
- Use FastAPI's `TestClient` + in-memory repo fakes mirroring `tests/extractors/test_extractor.py:_InMemoryPostingRepo` style. No real DB.

LoC est: 600 incl. tests.

### PR4 — `feat: Chrome MV3 extension skeleton`

First extension PR. Zero portal-specific logic. Establishes the bones.

New top-level directory at repo root: `extension/`. Contents:
```
extension/
├── manifest.json
├── background/
│   └── service-worker.js       # message router + (stub) detail fetcher
├── content-scripts/            # per-portal scripts land in PR5/PR7/PR8
├── popup/
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
├── options/
│   ├── options.html
│   └── options.js              # configures JMI URL + ingest token
├── lib/
│   ├── jmi-client.js           # fetch wrapper for /api/{ingest,details,health}
│   ├── toast.js                # notifications via chrome.notifications.create
│   └── rate-limiter.js         # stub class signature; impl in PR6
├── icons/
│   ├── 16.png                  # placeholder icons (single color)
│   ├── 48.png
│   └── 128.png
└── README.md                   # how to load unpacked
```

`manifest.json` highlights:
- `manifest_version: 3`
- `permissions: ["storage", "activeTab", "notifications"]`
- `host_permissions: []` initially empty
- `optional_host_permissions: ["https://justjoin.it/*", "https://nofluffjobs.com/*", "https://www.linkedin.com/*", "http://127.0.0.1:8000/*"]` — user grants per-host on first use
- `background.service_worker: "background/service-worker.js"`, `type: "module"` (ES modules)
- `action.default_popup: "popup/popup.html"`
- `options_page: "options/options.html"`
- `content_scripts: []` initially empty (registered per-portal in later PRs)

Popup contents:
- "Save jobs on this page" button (disabled with explanation if not on a known listing URL — popup checks `chrome.tabs.query({active: true})` and matches against allowlist)
- "JMI status: connected | unreachable" indicator (calls `/api/health` on popup open via `jmi-client.js`)
- Link to options page
- Last save: "12 jobs saved at 14:32" (read from `chrome.storage.local`)
- Last 3 errors with "Retry failed details" button (PR6 wires this up)

Service worker responsibilities (skeleton in PR4, fleshed out in PR5/6):
- Listen for `chrome.runtime.onMessage`
- Action `INGEST_LISTING` (from popup/content script): receive parsed cards, POST to `/api/ingest`, store stats in `chrome.storage.local`. Skeleton just logs + replies "ok" (no real fetch in PR4).
- Action `INGEST_DETAILS`: trigger detail fetch loop. Stub in PR4; implemented in PR6.
- Action `HEALTH_CHECK`: GET `/api/health`, reply.

Storage keys:
- `chrome.storage.local`: `lastSave: {ts, count, source}`, `errors: [{ts, url, reason}, ...]` (rolling 50)
- `chrome.storage.sync`: `jmiUrl: "http://127.0.0.1:8000"`, `ingestToken: "..."` (set in options page)

Acceptance: load unpacked, popup opens, "JMI unreachable" if backend not running; "JMI connected" when `jmi serve` is up. No portal scripts active yet.

LoC est: 400.

### PR5 — `feat: JJIT content script + parser`

First portal integration. Validates the end-to-end flow with one real portal.

Files added:
- `extension/content-scripts/jjit.js` — content script for `*://justjoin.it/*`
- `extension/lib/parsers/jjit-listing.js` — DOM → `IngestPostingIn[]` (testable in isolation)

`manifest.json` updates:
- Append to `content_scripts`: `{"matches": ["https://justjoin.it/*"], "js": ["lib/parsers/jjit-listing.js", "content-scripts/jjit.js"], "run_at": "document_idle"}`

Logic:
- On load, content script does NOT auto-parse (HITL invariant). It registers a `chrome.runtime.onMessage` listener.
- When popup sends action `PARSE_LISTING`, content script:
  1. Locates job-card container (per §3 selectors)
  2. Iterates cards, extracts per-card fields
  3. Replies with array of partial postings + `{cardCount, errors}` summary
- Service worker receives the array, POSTs to `/api/ingest`, stores result in `chrome.storage.local`, surfaces toast.
- If `IngestResponse.accepted > 0`, SW immediately enqueues `INGEST_DETAILS` action for those URLs (PR6 implements).

Tests (`extension/__tests__/jjit-listing.test.js`):
- Use vitest + jsdom (matches modern JS testing in lieu of Jest)
- Fixture HTML snapshots in `extension/__tests__/fixtures/jjit-listing-*.html` (anonymized: company names → synthetic, URLs → `https://example.test/...`)
- Tests: parses N cards from N-card fixture, missing optional fields don't crash (location_raw, salary_raw nullable), virtualized scroll partial DOM doesn't double-count, invalid card (missing title) gets logged not thrown

Verification:
- Manual smoke: navigate to https://justjoin.it/all-offers, scroll through 50 jobs slowly (so virtualized list hydrates them), click "Save jobs on this page", observe toast "50 jobs ingested"; `psql` confirms `count(*) WHERE source='jjit' AND description_text IS NULL = 50`.

LoC est: 350 incl. tests + fixtures.

### PR6 — `feat: background detail fetcher with rate limiting`

Closes the loop. URLs from PR5 ingest get filled with full descriptions.

Files added/changed:
- `extension/background/detail-fetcher.js` (new)
- `extension/background/offscreen.html` + `extension/background/offscreen.js` (new — DOMParser context)
- `extension/background/service-worker.js` — wire `INGEST_DETAILS` action to `detail-fetcher.js`, manage offscreen document lifecycle
- `extension/lib/parsers/jjit-detail.js` (new) — fetched HTML → `description_html` + `description_text` (port of the Quill-aware walker from `docs/_archived/jjit-plan-abandoned.md` §6, ~30 lines)
- `extension/lib/rate-limiter.js` — implementation (was stub in PR4)

Logic:
- After successful `POST /api/ingest`, SW invokes detail-fetcher with URL list.
- For each URL, queue through `RateLimitedQueue({minGapMs: 500, maxConcurrent: 25})` (per §5).
- Each task:
  1. `fetch(url, {credentials: "include"})` (browser context, user's session — JJIT detail pages are public so no login required)
  2. Send response HTML to offscreen document via `chrome.runtime.sendMessage` (offscreen has `DOMParser`); offscreen returns parsed `{description_html, description_text, raw_payload_patch}`
  3. Push into batch buffer; flush via `POST /api/details` every 25 details OR every 5s, whichever comes first
- On per-URL failure (network, 4xx, 5xx, parse fail): record in `chrome.storage.local.errors` rolling buffer, continue.
- On 429: 1 immediate retry with 5s delay; if still fails, push to errors for manual "Retry failed details" action.

Rate limiter implementation (`extension/lib/rate-limiter.js`):
```javascript
export class RateLimitedQueue {
  constructor({ minGapMs = 500, maxConcurrent = 25 } = {}) { ... }
  async add(asyncFn) { /* respects both minGapMs between *starts* and maxConcurrent in-flight */ }
}
```
Tests: simulate 100 enqueued tasks with synthetic 1s response; assert no two starts within 500ms, no more than 25 in flight at any tick, all eventually complete.

Offscreen document: MV3 service workers lack `DOMParser` and `document`. The offscreen document API gives a hidden DOM context. Its lifecycle is managed by SW (`chrome.offscreen.createDocument(...)`); single offscreen doc serves all detail parses for the run, closed when batch is done.

Budget: ~2 evenings of dev (offscreen document API research + rate limiter + parser dispatch + tests).

Verification: PR5 manual smoke + 30-60s wait → toast "50 details filled" → `psql` confirms `count(*) WHERE source='jjit' AND description_text IS NOT NULL = 50`.

LoC est: 450.

### PR7 — `feat: NFJ content script + parser`

Mirrors PR5 for NFJ. Same structure, different DOM selectors.

Files added (mirroring PR5 + PR6 portal-specific bits):
- `extension/content-scripts/nofluff.js`
- `extension/lib/parsers/nofluff-listing.js`
- `extension/lib/parsers/nofluff-detail.js`
- Tests + fixtures

`manifest.json` updates: add NFJ matches block.

`detail-fetcher.js` updates: dispatch parser by source (`jjit-detail.js` vs `nofluff-detail.js`).

Verification: same as PR5 for `https://nofluffjobs.com/`.

LoC est: 350.

### PR8 — `feat: LinkedIn content script (deferred to second wave)`

Deferred because:
- LinkedIn has aggressive anti-bot detection. `fetch()` from SW may hit captcha even with user session.
- Listing page DOM changes frequently (LinkedIn iterates UI weekly).
- Auth required to view full descriptions — extension must operate in user's logged-in session reliably.

Acceptable to defer: PR1-7 ship a working ToS-clean Polish-market pipeline. LinkedIn lands when there's appetite to debug it. Possibly never — depends on whether LinkedIn data adds value over JJIT/NFJ.

LoC est: 400 (when it lands).

## 3. DOM selector research

### Status

**Deferred to PR5/PR7 dev work.** User does DevTools inspection at the start of those PRs (15-min task per portal). MCP-driven inspection was attempted in the plan-mode session but failed (extension permission gate + SPA hydration latency); not worth retrying for a one-time research task.

### Inspection brief — what user records before PR5/PR7

For each portal, open in Chrome → DevTools (F12) → Elements panel. Record selectors in a `selectors.md` file alongside the parser, with date observed.

#### JJIT (`https://justjoin.it/all-offers`)

| Selector role | What to find | Verification command (paste in DevTools Console) |
|---|---|---|
| Card container | Single ancestor wrapping all visible cards. Likely `[data-testid="virtuoso-item-list"]` or similar (JJIT uses Virtuoso for virtualized scroll) | `document.querySelectorAll('CONTAINER > *').length` ≈ visible card count |
| Single card | Repeating element = one offer. Likely `[data-test-id]` or `[role="listitem"]` | Click highlights one job |
| Title | Within card, element with the role title | `card.querySelector('SEL').textContent` returns the title string |
| Company name | Company name within card | as above |
| Salary range | "16 000 - 24 000 PLN" string | as above |
| Location | City + Remote/Hybrid/Onsite badge | as above |
| Tech tags | Tech stack pills (Python, React, ...) | `card.querySelectorAll('SEL').length` returns pill count |
| Detail page URL | `<a href="...">` to offer page | `card.querySelector('a').getAttribute('href')` returns relative URL like `/job-offer/python-developer-...` |
| Pagination signal | How does JJIT signal "no more"? (Virtualized — likely no traditional pagination; bottom-of-list sentinel?) | Scroll to bottom, observe behavior |
| Stable ID | Is the JJIT `guid` (UUID) present in DOM as a `data-*` attribute? Or only in fetched API response? | `card.dataset` shows all data attributes. If guid not in DOM, fallback `source_id = url.slug` parsed from href |

**Critical note on JJIT virtualized scroll**: cards outside viewport are NOT in DOM. Implication: extension parses **only what's currently visible/scrolled-through**. User must scroll through all cards they want saved before clicking "Save jobs on this page." Document prominently in popup UI ("Scroll all the way through, then click Save").

#### NFJ (`https://nofluffjobs.com/`)

Same table as above. NFJ's listing historically uses Angular components — selectors may include `nfj-postings-list`, anchor-as-card pattern, etc. User to verify in DevTools.

Pagination: NFJ likely uses "load more" button OR infinite scroll. Either way, principle is the same: parse what's loaded, user navigates more pages = more clicks.

#### LinkedIn (deferred to PR8)

Listing at `/jobs/search/`. Historically stable attributes: `data-occludable-job-id` (numeric), `aria-label` on cards. User to verify when PR8 lands; LinkedIn changes selectors frequently so plan to revalidate.

### Selector resilience strategy
- **Prefer**: `data-test`, `data-testid`, `aria-label`, `role`, `aria-*` — designed for testing/accessibility, less likely to churn
- **Avoid**: minified CSS classes (`.css-1a2b3c`), `:nth-child()` positional selectors
- **Document each selector** in a comment with date observed + portal version visible (e.g. `// 2026-05-14, JJIT all-offers, container = data-testid="virtuoso-item-list"`)
- **Fallback**: if primary selector returns 0 cards, log to error queue, surface in popup ("JJIT layout changed — parser needs update; see chrome.storage.local.errors")

## 4. CORS handling

`POST /api/ingest`, `POST /api/details` are cross-origin from extension (origin: `chrome-extension://<id>`) to backend (origin: `http://127.0.0.1:8000`).

FastAPI middleware (in `src/jmi/api/app.py`):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*"],   # MV3 extensions
    allow_credentials=False,                   # X-Ingest-Token in header, no cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Ingest-Token"],
    max_age=3600,                              # cache preflight for 1h
)
```

Notes:
- Wildcard origin works because `allow_credentials=False`. CORS spec forbids wildcard + credentials together.
- Preflight (OPTIONS) is automatic — extension's POST with `Content-Type: application/json` is a non-simple request and triggers preflight. Middleware handles.
- `chrome-extension://*` wildcard support in FastAPI's CORSMiddleware varies by version. Fallback: pin the extension ID once it's stable after first dev load (`chrome://extensions/` shows the ID).

## 5. Background fetch rate limiting

User spec: "500ms between detail fetches, max 25 concurrent."

**Reconciliation** (the two numbers superficially conflict — 500ms gap implies sequential, 25 concurrent implies parallel):
- 500ms = minimum gap between *starts* of new requests
- 25 concurrent = upper bound on in-flight count
- Steady-state concurrency = `min(detail_response_time / 500ms, 25)`. For typical detail page (~1-2s response), expected concurrency = 2-4. The 25 cap is an upper guardrail for slow pages (response > 12.5s).

Implementation in `extension/lib/rate-limiter.js`:
```javascript
export class RateLimitedQueue {
  constructor({ minGapMs = 500, maxConcurrent = 25 } = {}) {
    this._minGapMs = minGapMs;
    this._maxConcurrent = maxConcurrent;
    this._lastStart = 0;
    this._inFlight = 0;
    this._pending = [];
  }

  async add(asyncFn) { /* respects both gap + concurrency, returns asyncFn's result */ }
}
```

**Politeness considerations:**
- 500ms gap is more conservative than typical browser behavior (browsers do ~6 parallel HTTP/1.1 conns per host with no gap; HTTP/2 multiplexes).
- Combined with 25 concurrency cap, even under fastest portal, we're at ~50 req/sec ceiling. JJIT listing pages serve real browser traffic at much higher aggregate rates.
- User can override `minGapMs` in extension options if a portal complains. Defaults stay polite.
- If a portal returns 429 with `Retry-After`, the per-task retry waits that long before retrying once; on second 429, push to errors — don't sleep an hour mid-run.

## 6. Error handling

### Extension side (toasts + popup logs)
`extension/lib/toast.js` exports `showToast({type: "ok"|"err"|"warn", text, ttlMs=4000})`. Surfaces via `chrome.notifications.create()` (system tray) plus an in-popup banner with last 3 messages.

Cases:
| Trigger | Toast text |
|---|---|
| Network unreachable on /api/ingest | "JMI unreachable. Is `jmi serve` running?" |
| 401 from backend | "Ingest token mismatch. Set token in extension options." |
| 422 (validation) on N postings | "{accepted} jobs saved, {invalid} had invalid data — see popup." |
| Detail fetch failures (mid-batch) | "{ok} of {total} details fetched. {failed} failed — see popup." |
| Health check fail on popup open | "JMI offline" status indicator + popup explanation |

All errors also stored in `chrome.storage.local.errors` (rolling 50) with `{ts, source, action, url|sourceId, reason}`.

### Backend side (structured logs, mirroring existing `scrape.*` naming)
- `ingest.received` — count, source
- `ingest.skip.existing` — source, source_id
- `ingest.skip.invalid` — source, source_id, errors
- `ingest.done` — count_inserted, count_skipped, count_invalid
- `details.received` — count, source
- `details.skip.unknown` — source, source_id (POST'd a detail for posting we don't have — extension bug or race)
- `details.done` — count_updated, count_skipped, count_invalid
- `health.check` — db_ok

### Per-URL detail retry
Popup has "Retry failed details" button → reads `chrome.storage.local.errors` filtered to detail-fetch failures, re-runs them. Backend POST `/api/details` is idempotent for already-filled rows (update_description overwrites — acceptable for v1; if we want strict idempotence, add `WHERE description_text IS NULL` to the UPDATE).

## 7. Data model

### Flow
1. Extension content script parses listing page → array of `IngestPostingIn`
2. SW POSTs batch to `/api/ingest`. Backend creates `JobPosting` rows with `description_html=NULL`, `description_text=NULL`. Returns counts + invalid index list.
3. SW iterates URLs (only those that came back as accepted, not skipped_existing), fetches each via browser `fetch(url, {credentials: "include"})`. Parses body in offscreen document via portal-specific detail parser → `IngestDetailIn`.
4. SW POSTs batch to `/api/details` (every 25 details or every 5s). Backend updates matching `JobPosting` rows in place via `repo.update_description(...)`.
5. User runs `jmi extract -n N` (existing CLI). Extractor sees rows with non-NULL `description_text`, processes via Anthropic. The new "skip empty description" guard is included in PR3 (one-line change in `src/jmi/extractors/anthropic.py`).

### Schema
No new tables. `JobPosting` table reused. Two changes (already covered):
- `description_html`, `description_text` made nullable (PR2 migration)
- `Source` literal widened (PR3)

### Partial state semantics
A `JobPosting` row with `description_text IS NULL` represents "ingested from listing, awaiting detail fetch." Structurally identical to the deferred JJIT plan's intermediate state; same query (`list_pending_details`), same resilience properties.

If detail fetch fails permanently for some URL, the row stays with NULL description. Extractor's empty-description skip prevents wasted Anthropic spend. Future "retry failed details" is via the extension popup button (§6), no backend cron needed.

## 8. Open questions (decide before implementation; recommendations attached)

1. **Pagination signal for JJIT (virtualized)**
   - Recommendation: trust user — parse what's in DOM at the moment of click. Add UI hint "Scroll through all jobs you want to save before clicking."
   - Alternative: extension scrolls to bottom on user click before parsing. Rejected — re-introduces automation.

2. **`source_id` per portal**
   - JJIT: `guid` if present in DOM as `data-*`, else parsed slug from URL. Verify in §3 inspection.
   - NFJ: URL slug hash (e.g. `(company)-(role)-(8charhash)` — the hash is the stable ID).
   - LinkedIn: `data-occludable-job-id` numeric attribute.

3. **Background fetch error retry policy**
   - Recommendation: 1 immediate retry with 5s delay on 429/5xx; if still fails, push to error queue for manual "Retry failed details" action.
   - Alternative: exponential backoff with N attempts. Rejected — adds complexity, the manual retry button covers the same ground for v1.

4. **Popup behavior when active tab is not on a listing page**
   - Recommendation: detect via `chrome.tabs.query({active: true})`, match URL against known patterns; if no match, disable Save button and show "Navigate to a job listing page first" with examples.

5. **Token rotation**
   - Recommendation: shared `JMI_INGEST_TOKEN` env var on backend + extension options. On rotation, update both. Acceptable for personal use.
   - Alternative: OAuth. Rejected — overkill for localhost personal tool.

6. **`src/jmi/sources/wellfound/` empty stub directory**
   - Recommendation: leave untouched. Decide in Week 3 retro: if Wellfound API turns out ToS-clean, fill the stub with an HTTP scraper; if not, convert to a content script under the extension path.

7. **MV3 service worker lifetime**
   - Recommendation: trust MV3's "keep alive while fetch operations pending" semantics. Verify with a manual 100-URL test in PR6 dev. If SW dies mid-batch, fallback: split batches into 25-URL chunks each posted independently (we already POST in batches of 25, so this is mostly already handled).

8. **CORS allow_origins wildcard pattern**
   - Recommendation: try `["chrome-extension://*"]` first. If FastAPI's CORSMiddleware doesn't accept wildcard subpath, fall back to listing the extension's stable ID after first dev load (`chrome://extensions/` shows the ID; pin it in `.env`).

## 9. PR sequence summary

| PR | Title | Type | LoC est | Reviewer focus |
|---|---|---|---|---|
| 1 | docs: ADR-0009 HITL ingestion pivot | docs | 250 | Legal framing, regulamin quotes, webclipper precedent |
| 2 | feat: Alembic adoption + nullable description columns | infra | 200 | Migration correctness, backward-compat with Week 1 data (pg_dump preflight) |
| 3 | feat: FastAPI ingest endpoint | feat | 600 | API contract, CORS, auth, dedup, repo update_description |
| 4 | feat: Chrome MV3 extension skeleton | feat | 400 | Manifest, popup UX, message routing, no portal logic |
| 5 | feat: JJIT content script + parser | feat | 350 | Selector resilience, parser tests with fixture HTML |
| 6 | feat: background detail fetcher + rate limiting | feat | 450 | Rate limiter correctness, offscreen document for DOMParser, error retry |
| 7 | feat: NFJ content script + parser | feat | 350 | Same as PR5, NFJ-specific |
| 8 | feat: LinkedIn content script | feat (deferred) | 400 | Anti-bot resilience, auth handling |

Total: ~3000 LoC across 8 PRs, ~2 weeks of dev sessions.

## 10. End-to-end verification (after PR7 merges)

```bash
# Backend up
docker compose up -d
uv run alembic upgrade head
uv run jmi serve &        # FastAPI on 127.0.0.1:8000

# Health check
curl http://127.0.0.1:8000/api/health
# Expected: {"status":"ok","db_ok":true,"version":"0.1"}

# Extension loaded via chrome://extensions/ → "Load unpacked" → select extension/
# Open extension options page, set JMI URL + ingest token

# JJIT round trip
# Navigate to https://justjoin.it/all-offers, scroll through 50 jobs slowly
# Click extension icon → "Save jobs on this page"
# Toast: "50 jobs ingested, fetching details..."
# Wait ~30s
# Toast: "50 details filled."
psql $DATABASE_URL -c "SELECT count(*) FROM job_postings WHERE source='jjit' AND description_text IS NOT NULL;"
# Expected: 50

# Run extractor (existing pipeline)
uv run jmi extract -n 50
# Expected: 50 extracted, 1 cache miss + 49 cache hits (cold cache miss on first row)

# Same for NFJ
# Navigate to https://nofluffjobs.com/, scroll 50 jobs, click save, repeat
psql $DATABASE_URL -c "SELECT source, count(*) FROM job_postings GROUP BY source;"
# Expected: huggingface | <existing>, jjit | 50, nofluff | 50
```

## Open uncertainties to validate empirically

1. **JJIT and NFJ DOM selectors** (§3) — needs DevTools inspection by user at start of PR5 / PR7.
2. **JJIT virtualized scroll behavior** — does scrolling hydrate cards persistently, or are they GC'd when scrolled past? Affects PR5 manual smoke test.
3. **NFJ pagination model** — buttons vs infinite scroll vs "load more". Decides UX hint in popup.
4. **MV3 service worker lifetime under sustained fetch load** (§8 question 7).
5. **Whether `fetch()` in SW respects browser cookies** — should be yes via `credentials: "include"` but verify for JJIT/NFJ specifically (their detail pages are public so probably moot).
6. **Whether JJIT/NFJ detail pages load full body HTML on initial fetch or require client-side hydration** — if hydration, our SW fetch returns a skeleton; fallback is to send `description_html=""` and let extractor handle gracefully (the empty-description skip catches it).
7. **CORS wildcard subpath support in FastAPI middleware** (§4 / §8 question 8).
8. **NFJ regulamin § 2 ust. 9 exact wording** — confirm verbatim text for ADR-0009 quote (≤14 words, in quotation marks).

## Critical files (for implementation reference)

- [src/jmi/sources/huggingface/scraper.py](src/jmi/sources/huggingface/scraper.py) — HF scraper pattern (NOT touched by this plan; coexistence)
- [src/jmi/storage/jobs.py](src/jmi/storage/jobs.py) — repository extensions land here (PR3)
- [src/jmi/db/models.py](src/jmi/db/models.py) — schema mutations (PR2)
- [src/jmi/cli.py](src/jmi/cli.py) — `jmi serve` command added (PR3)
- [src/jmi/models/job.py](src/jmi/models/job.py) — Source literal extension (PR3)
- [src/jmi/extractors/anthropic.py](src/jmi/extractors/anthropic.py) — empty-description skip (PR3)
- [docs/adr/0006-extraction-pipeline-architecture.md](docs/adr/0006-extraction-pipeline-architecture.md) — separated pipeline ADR, still applies
- [docs/adr/0008-jjit-removed-from-phase-1.md](docs/adr/0008-jjit-removed-from-phase-1.md) — sets up the legal framing for ADR-0009
- [docs/_archived/jjit-plan-abandoned.md](docs/_archived/jjit-plan-abandoned.md) — pattern reuse source for parser (Quill walker §6) and repo (`update_description`, `list_pending_details` §9)
