> **Status: ARCHIVED — not implemented.**
> **Why archived:** see [ADR-0008: JJIT Removed from Phase 1](../adr/0008-jjit-removed-from-phase-1.md).
>
> This document is the verbatim output of the Week 2 plan-mode session for the JustJoinIT scraper. After completing the technical plan, ToS / robots.txt diligence on JJIT (point 11.3 of the regulamin + the `Disallow: /api/` rule) gave an unambiguous "no" from the operator. JJIT was dropped from Phase 1; NoFluffJobs was promoted from Week 3 to Week 2.
>
> **Why preserved:** ~80% of the architectural decisions below (Alembic-first migration, separated 3-step pipeline, multi-company mapper, Quill-aware HTML parser, structured-vs-LLM Option A) are portable to NFJ with portal-specific changes only. The NFJ planning session reuses this artifact rather than re-deriving the patterns.

---

# JJIT Scraper — Implementation Plan (Week 2)

## Context

Week 2 of Phase 1. Week 1 shipped: `JobPosting` / `JobExtract` models, SQLAlchemy ORM, `JobPostingRepository` / `JobExtractRepository`, HF Jobs scraper (single-call list endpoint), Anthropic LLM extractor with prompt caching, `jmi scrape | extract | init-db` CLI. JJIT is the second source — and the actual job-hunt target portal — so the scraper has to ship even though it's harder than HF technically.

What's empirically verified (by user, via real `curl`):
- List endpoint `GET /api/candidate-api/offers` is unauthenticated, returns paginated `{data: [JobListItem], meta: {totalItems, prev: {cursor}}}`. Page size up to 100 (cap not yet validated). Salary, seniority, workplace type, skills, category all returned structured.
- Detail endpoint `GET /api/candidate-api/offers/{slug}` is unauthenticated, returns the same `JobListItem` shape plus `body` (HTML, possibly Polish) and a few company fields.
- `guid` (UUID) is stable per offer and present in both list and detail. It is the right idempotency key — slugs can change.
- Scale: 100 offers = 1 list + 100 detail HTTP calls. Detail endpoint is the rate-limit bottleneck.

What's not verified (flagged in §10 / §11 — needs eyes before code):
- ToS at `https://justjoin.it/regulamin` — returned 404 in WebFetch. Real URL needs to be located manually.
- Public URL pattern for an offer page (`https://justjoin.it/job-offer/{slug}` is a guess from the brief).
- Whether the JSON `body` field is plain HTML or some richer structure (e.g. Quill delta).

---

## 0. CRITICAL FINDING (decision required before any code)

`https://justjoin.it/robots.txt` contains:

```
User-agent: *
Disallow: /api/
```

Plus six other paths (`/admin/`, `/templates`, `/_styles`, etc.). **The `Disallow: /api/` rule explicitly covers the `/api/candidate-api/offers` endpoint we'd be hitting.**

robots.txt is advisory, not a legal contract — but it's a clear signal from the operator. Three honest interpretations, with my read of each:

**(a) Respect robots.txt strictly → don't scrape JJIT API.**
Move JJIT off the roadmap; either (i) jump to NoFluffJobs (Week 3 in original plan) and revisit JJIT later, or (ii) drop JJIT entirely.
Pros: zero ToS risk, cleanest. Cons: loses the actual job-hunt target portal, blows up the Phase 1 portal-order plan in CLAUDE.md.

**(b) Distinguish "Disallow for indexers" vs "API for clients."**
Robots.txt was designed for crawlers (Googlebot et al.) so search engines don't index API responses. A purpose-built scraper accessing a public, unauthenticated JSON API at human-scale rates is arguably a different category. Many sites Disallow `/api/` for SEO hygiene, not to ban programmatic use.
Pros: pragmatic, matches widespread industry practice for personal-use scrapers. Cons: it is still ignoring an explicit operator signal — interpretation, not adherence.

**(c) Proceed only after manual ToS check tilts in our favor.**
Read regulamin (need correct URL — `/regulamin` 404'd; try footer of justjoin.it for the right link), look for explicit "no automated access" language. If silent, lean (b). If explicit prohibition, pivot to (a).

**My recommendation: (c).** It's the only interpretation that gathers the missing evidence. Concretely: spend 10-15 minutes reading regulamin in browser before any code. Decision points:
- If ToS explicitly forbids automation → abandon JJIT, pivot to NoFluffJobs in Week 2, document in an ADR ("ADR-0008: JJIT removed from Phase 1, robots.txt + ToS basis").
- If ToS is silent → proceed with the plan below, with conservative rate limits (§7) and a documented "bot identifies itself, exits cleanly on 4xx" stance (§10). Add a `JMI_DISABLED_SOURCES` kill switch in env.
- If ToS allows API for personal/non-commercial use → proceed normally.

Everything below assumes the decision lands "proceed." If we abandon, this plan becomes the NoFluffJobs plan with a different mapper.

---

## 1. Schema / migration strategy

### Recommendation: adopt Alembic now as the first PR of Week 2

**Why now.** JJIT is the first real schema-altering change (new source value, nullable description columns). The current `jmi init-db` path means a destructive `DROP/CREATE` against the local DB containing Week 1 HF data and extracts. Once NoFluffJobs (Week 3) lands, the cost of not having migrations compounds — every `ALTER TABLE` becomes a coordination problem between dev DB and the planned testcontainers fixture (`tests/conftest.py` already mentions Week 2 testcontainers). Week 1 retro lists Alembic as a Week 2 priority *before* JJIT.

**Alternative (rejected): edit `db/models.py` + `init-db` drop-and-recreate.** Faster today (~30 min vs ~2h). Loses Week 1 HF rows + extracts (small, but real Anthropic spend). Pushes the same problem into Week 3 under more pressure.

**Migration sequence**:

1. `uv add alembic`. `alembic init src/jmi/db/migrations` (src-layout — keeps migrations inside the installed package). Configure `env.py` to import `Base` from `jmi.db.base` and read `DATABASE_URL` from `jmi.config.get_settings()`. Replace `init-db` body with `command.upgrade(cfg, "head")`.
2. Migration 0001 — baseline. `alembic revision --autogenerate -m "baseline"`. Should match current `Base.metadata` exactly. On the live dev DB run `alembic stamp head` (don't re-execute DDL — the tables already exist; we just want Alembic's bookkeeping table primed).
3. Migration 0002 — JJIT prerequisites. Two changes:
   - `description_html` and `description_text` → nullable. (`ALTER COLUMN ... DROP NOT NULL`.) Required for the separated pipeline (§2) so list-only inserts pass.
   - Source literal in `src/jmi/models/job.py:9` is widened to `Literal["huggingface", "wellfound", "jjit"]`. Postgres column is `String(32)` (not a PG enum) so this is a Python-only change — but worth a no-op migration entry that documents it.

**Uncertainty**: Alembic autogenerate sometimes misses `__table_args__ = (UniqueConstraint(...),)` and the `JSONB` vs `JSON` distinction. Run `alembic upgrade --sql` dry-run before committing 0001 and eyeball the SQL.

**Tidy-up worth flagging (out of scope for this plan)**: `JobExtractORM.tech_stack` uses `JSON` (`db/models.py:51`) while `raw_payload` uses `JSONB` — inconsistent, no functional impact today, fix in a future migration.

---

## 2. Pipeline design: separated 3-step (recommendation)

### Recommendation: three commands — `scrape` → `fetch-details` → `extract`

**Why.** ADR-0006 already mandates separation between scrape and extract. JJIT economics make the case for a *third* split: list = 1 HTTP call for 100 rows, detail = 100 HTTP calls. If detail rate-limits trip on call 47, with single-pass we lose the list metadata we already retrieved (have to re-paginate). With separation, the 100 list rows are durable in DB; we resume detail fetch from where we stopped via `WHERE description_text IS NULL`. This is exactly the failure-containment argument from ADR-0006 §"Positive bullets," extended one stage further.

Bonus: separation lets us run `jmi scrape -s jjit -n 100` cheaply and inspect the list rows in DB before committing to the expensive detail fetch — useful while we're still calibrating filters and rate limits.

**Alternative (rejected): single-pass to match HF.** No schema change needed, simpler. But HF returns full descriptions inline — there's no analogue to "detail fetch" to defer. Forcing JJIT into the HF mold conflates two genuinely different data shapes and concentrates the rate-limit risk in a single command.

**Alternative (rejected): 2-step (scrape pulls list+detail in one command, extract separate).** Compromise — keeps `description_text NOT NULL`, no migration, but loses the resume-from-failure property. Same code cost as 3-step, less value.

### Exact contracts

```
jmi scrape -s jjit -n N
```
- Fetches list pages until `N` jobs collected or `meta.totalItems` exhausted.
- Maps each `JobListItem` → `JobPosting` with `description_html=None`, `description_text=None`.
- Stores list metadata in `raw_payload` (whole list item dict, untouched).
- Idempotent via `repo.get_by_source("jjit", guid)`.
- Logs: `scrape.fetched`, `scrape.page.done`, `scrape.skip.invalid`, `scrape.skip.existing`, `scrape.done`. Mirror HF event names.
- Returns `ScrapeStats(inserted, skipped, invalid, pages_fetched)`.

```
jmi fetch-details -s jjit -n N --rate 0.5
```
- Queries `JobPostingRepository.list_pending_details(source="jjit", limit=N)` (§5) — oldest-first FIFO.
- For each: GET `/offers/{slug}`, parse `body` HTML → text (§6), **UPDATE in place** via new `repo.update_description(id, html, text, raw_payload_patch)` (§5).
- `raw_payload` merge: keep the original list item, add `{"detail": detail_dict}`. Recoverable for ground-truth dataset.
- Sleeps `--rate` seconds between detail requests (default 0.5s = 120 req/min, see §7).
- Returns `FetchStats(updated, skipped_no_body, invalid, failed_api_calls)`.
- Idempotent: query inherently skips rows already filled.

```
jmi extract -n N
```
- Unchanged behavior, plus one safeguard: extractor skips postings where `description_text` is None or empty, with `extract.skip.no_description` log line. One-line change in `extractors/anthropic.py`. Promotes to a repo-side `list_pending_extract` method later if it becomes noisy.

---

## 3. Structured data treatment: Option A (raw_payload only)

### Recommendation: keep all structured fields in `raw_payload`, no new columns

JJIT returns `experienceLevel`, `workplaceType`, `requiredSkills` (with proficiency 1-5), `employmentTypes` (salary), `category`. The raw_payload column is JSONB — these fields are queryable in Postgres in microseconds via `raw_payload->>'experienceLevel'`. The Phase 3 eval value (LLM-vs-truth comparison) is fully captured:

```sql
SELECT extract.seniority, posting.raw_payload->>'experienceLevel'
FROM job_extracts extract
JOIN job_postings posting ON posting.id = extract.job_posting_id
WHERE posting.source = 'jjit' AND extract.seniority != posting.raw_payload->>'experienceLevel';
```

That gives the same bug-detection signal Option B's structured columns would.

**Why not Option B (new structured columns + LLM independent + eval).** Best long-term, premature now. Costs:
- Schema bloat (5 new nullable columns) before the eval framework that justifies them exists.
- Locks JJIT's taxonomy values (`workplaceType` enum) into our schema — exactly what ADR-0005/0006 design tried to prevent. NoFluffJobs (Week 3) will use *different* enum values; we'd need a normalization layer per source.
- Two sources of truth for the same field (`workplace_type` from JJIT raw vs `remote_policy` from LLM) without a downstream rule for which wins — invites silent dashboard divergence.

**Why not Option C (fast-path skip LLM for structured fields).** Tempting (~30% Anthropic cost savings on JJIT). Rejected because:
- Makes the extractor source-aware (smell — it's source-agnostic by design today).
- Makes Phase 3 eval strictly harder (per-field provenance: "which path produced this?").
- Prompt-cache prefix savings already give Opus 4.7 at near-Haiku marginal cost — savings are modest in absolute terms.

**Documented as deferred ADR-0007 candidate**: "Structured-data taxonomy normalization — adopt cross-source canonical fields when NFJ (Week 3) gives the second data point."

**Uncertainty**: Postgres JSONB `->>` queries on `raw_payload` may need a GIN index (`USING gin (raw_payload jsonb_path_ops)`) at scale. Skip the index for v1 (we're at <10k rows); add when dashboards (Phase 2) get sluggish.

---

## 4. Multi-company refactor

JJIT is multi-company; each list item has `companyName`. HF was single-company with `SOURCE_COMPANY = "Hugging Face"` as a class attribute on the scraper passed to the mapper. JJIT mapper reads `companyName` directly from the JSON.

Concrete changes:
- JJIT scraper class has `SOURCE = "jjit"` only — **no** `SOURCE_COMPANY`. Mapper signature differs from HF's: `to_partial_posting(list_item, *, scraped_at)` — no `company_name` param.
- `JobPosting.company_name` stays NOT NULL. JJIT mapper raises `pydantic.ValidationError` if `companyName` missing in the source payload (logged as `scrape.skip.invalid`).
- HF rows are unaffected — they still have "Hugging Face" baked in by the existing mapper.

No backward-compatibility migration needed.

---

## 5. Pagination + scale

**Approach**: offset-based pagination via `from` query param. Increment `from` by 100 each page until `len(data) == 0` or `from >= meta.totalItems` or user-supplied `--limit` reached.

Stop conditions (any of):
- `len(data) == 0`
- `from + len(data) >= meta.totalItems`
- accumulated inserts ≥ `--limit`
- accumulated pages ≥ 100 (hard safety cap = 10 000 rows = JJIT's documented cap; alarm via log if hit, since it means we may be missing data).

**Cursor (`meta.prev.cursor`) is deferred.** The cursor field is documented but we don't yet know its trigger condition. Add cursor support only if offset pagination produces duplicate or missing rows in the smoke test (validate by counting unique `guid`s vs sum of `len(data)` across pages).

**Incremental scrape** (e.g. `--since=...` or stop-when-guid-exists optimization) is deferred. v1 scrapes everything new every run; `get_by_source` skip handles dedup at insert time. Move to incremental when daily cron lands (Phase 2 / Week 5+).

---

## 6. HTML body → plain text

### Recommendation: structured walker emitting Markdown-flavored text

JJIT bodies are Quill-editor output (per the brief: `<p>`, `<strong>`, `<ul>/<li>`, `<em>`, classes `ql-header-2`, `ql-header-3`, `MsoNormal` from older Word-paste-derived listings). Naïve `bs4.get_text("\n", strip=True)` (HF's approach) flattens bullet lists into a wall of text — "Python Django Postgres" instead of `- Python\n- Django\n- Postgres`. That measurably degrades the LLM `tech_stack` extractor's recall on bullet-rich descriptions.

Parser sketch (~30 lines, in `html_parser.py`):

```python
from bs4 import BeautifulSoup

_HEADING_TAGS = {"h1", "h2", "h3", "h4"}
_HEADING_CLASSES = {"ql-header-2", "ql-header-3"}

def parse_jjit_body(html: str) -> str:
    """Convert JJIT description body to plain text with bullets and headings preserved."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for el in soup.find_all(True):
        classes = set(el.get("class") or [])
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in _HEADING_TAGS or classes & _HEADING_CLASSES:
            out.append(f"\n## {text}\n")
        elif el.name == "li":
            out.append(f"- {text}")
        elif el.name == "p":
            out.append(text)
    if not out:
        # Defensive fallback — JJIT changes structure, don't lose the description
        return BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    joined = "\n".join(out)
    while "\n\n\n" in joined:
        joined = joined.replace("\n\n\n", "\n\n")
    return joined.strip()
```

**Polish content**: no special handling at the parser level. BeautifulSoup is UTF-8 native; Pydantic `str` is unicode. The LLM (Opus 4.7) handles Polish fluently. The prompt's PLN normalization rule already covers salary edge cases. If extraction quality on Polish posts proves weak in Week 2 verification (§9), add Polish-specific examples to `extractors/prompt.py` in Week 3.

**Rejected: keep raw HTML, pass `description_html` to the LLM.** Doubles token cost, breaks the existing prompt-cache prefix invariant ("HTML already stripped").

---

## 7. Rate limiting

### Recommendation: `time.sleep(0.5)` between detail requests (120 req/min default), tenacity for retries

**Justification of 0.5s.** JJIT marketplace pages serve real browser traffic at much higher aggregate rates. A single client at 0.5s spacing is conservative (well below browser-implied burst rates) and finishes 100 details in ~50s. `--rate` flag exposes the knob: bump to `1.0` if blocked, drop to `0.25` if clean for 3 days.

**List endpoint**: no explicit throttle. We hit it a few times per scrape (once per 100 results); the gap between page calls is naturally wide enough.

**Tenacity config** (mirror HF's `WorkableClient`): `stop_after_attempt(5)`, `wait_exponential(multiplier=1, min=1, max=30)`, retry on `_RetriableHTTPError` (429 + 5xx) + `httpx.TransportError` + `httpx.TimeoutException`. Fail fast on other 4xx.

**429 with `Retry-After` header**: respect the header value as the wait time, not the exponential. Implement via custom exception carrying the wait, plus a `wait_fn` that picks `max(exponential, retry_after)`. ~10 lines added to `_raise_if_bad`.

### Pre-merge smoke test (5 sequential detail requests, manual)

```bash
uv run python -c "
from jmi.sources.jjit import JJITClient
c = JJITClient()
page = c.fetch_offers_page(offset=0, items_count=5)
import time
for o in page['data'][:5]:
    detail = c.fetch_offer_detail(o['slug'])
    print(o['slug'], '-', detail['title'], '-', len(detail.get('body','')))
    time.sleep(0.5)
"
```

Pass criteria:
- All 5 return 200, JSON parseable, `body` non-empty for at least 4/5.
- No `Retry-After` headers.
- Total wall time ~3-4s.
- No anti-bot HTML page (no `<title>Cloudflare</title>`, no 403 with HTML body).
- Manually open one slug in browser; verify body content matches the JSON.

If smoke passes, run a 50-detail test before committing the scraper PR.

---

## 8. Idempotency

| Stage | Mechanism | Repo method |
|---|---|---|
| List scrape | Skip if exists on (source=jjit, source_job_id=guid) | `repo.get_by_source` (existing) |
| Detail fetch | Query inherently filters: `WHERE description_text IS NULL AND source = 'jjit'` | `repo.list_pending_details` (new — §9) |
| Extract | Skip if `(posting_id, model_name)` exists | `repo.get_by_posting_and_model` (existing) |

`lastPublishedAt` re-update is **deferred** — premature optimization. Re-scrapes will skip; we don't update mutable fields on existing rows in v1.

---

## 9. Code structure

```
src/jmi/sources/jjit/
├── __init__.py          # re-exports for cli.py
├── client.py            # JJITClient — httpx + tenacity, list + detail endpoints
├── mapper.py            # to_partial_posting(list_item, *, scraped_at) → JobPosting
├── details.py           # merge_detail(posting, detail, parsed_text) → patch dict
├── html_parser.py       # parse_jjit_body(html) → str
└── scraper.py           # JJITListScraper, JJITDetailFetcher, ScrapeStats, FetchStats
```

**No `BaseScraper` abstract class** — rule of three (defer until NFJ in Week 3 gives the second data point).

### `__init__.py`

```python
from jmi.sources.jjit.client import JJITClient, JJITError
from jmi.sources.jjit.scraper import (
    JJITListScraper, JJITDetailFetcher, ScrapeStats, FetchStats,
)
__all__ = [...]
```

### `client.py`

```python
class JJITClient:
    BASE = "https://justjoin.it/api/candidate-api"
    def __init__(self, *, timeout=15.0, max_attempts=5, user_agent=None) -> None: ...
    def fetch_offers_page(self, *, offset: int, items_count: int = 100, currency: str = "pln") -> dict[str, Any]: ...
    def fetch_offer_detail(self, slug: str) -> dict[str, Any]: ...
    def close(self) -> None: ...
```

Single `httpx.Client` shared across both methods (TLS handshake amortization). Same Tenacity config as HF's `WorkableClient`. Custom UA + `Accept-Language: en;q=0.9, pl;q=0.8` headers (§10).

**404 on detail slug** is a non-retriable, non-fatal signal (offers get unpublished). Log `jjit.detail.gone`, surface to caller as a sentinel to count `skipped_no_body`.

### `mapper.py`

```python
def to_partial_posting(list_item: dict[str, Any], *, scraped_at: datetime) -> JobPosting:
    """JJIT JobListItem → JobPosting with description_* = None.
    Pure function. Raises pydantic.ValidationError on malformed input."""
```

- `source = "jjit"`
- `source_job_id = list_item["guid"]`
- `url = f"https://justjoin.it/job-offer/{list_item['slug']}"` (verify this pattern in browser before merge — could also be `/offers/{slug}`)
- `title = list_item["title"]`
- `company_name = list_item["companyName"]`
- `location_raw` = compose from `city` + `locations[]` (helper)
- `description_html = None`, `description_text = None` (after migration 0002)
- `posted_at = datetime.fromisoformat(list_item["publishedAt"])` if present else None
- `raw_payload = list_item` (whole dict — preserves all structured fields per §3)

### `details.py`

```python
def merge_detail(posting: JobPosting, detail: dict[str, Any], *, parsed_text: str) -> dict[str, Any]:
    return {
        "description_html": detail.get("body") or "",
        "description_text": parsed_text,
        "raw_payload": {**posting.raw_payload, "detail": detail},
    }
```

Pure function — testable in isolation, no I/O.

### `scraper.py`

```python
@dataclass
class ScrapeStats:
    inserted: int = 0
    skipped: int = 0
    invalid: int = 0
    pages_fetched: int = 0

@dataclass
class FetchStats:
    updated: int = 0
    skipped_no_body: int = 0
    invalid: int = 0
    failed_api_calls: int = 0

class JJITListScraper:
    SOURCE = "jjit"
    PAGE_SIZE = 100
    def __init__(self, client: JJITClient | None = None) -> None: ...
    def run(self, repo: JobPostingRepository, *, limit: int | None = None) -> ScrapeStats: ...

class JJITDetailFetcher:
    SOURCE = "jjit"
    def __init__(self, client: JJITClient | None = None, *, rate_seconds: float = 0.5) -> None: ...
    def run(self, repo: JobPostingRepository, *, limit: int | None = None) -> FetchStats: ...
```

Mirror HF's `_owns_client` pattern + `client.close()` in `finally` (`sources/huggingface/scraper.py:54-55`).

### Existing files to change

| File | Change | Reason |
|---|---|---|
| `src/jmi/models/job.py:9` | `Source = Literal["huggingface", "wellfound", "jjit"]` | Pydantic validation rejects `source="jjit"` without this. |
| `src/jmi/db/models.py:28-29` | `description_html`, `description_text` → `Mapped[str \| None]`, `nullable=True`. Mirror in Pydantic. | List-only inserts (§2). |
| `src/jmi/storage/jobs.py` | Add `list_pending_details(source, limit)` and `update_description(id, html, text, raw_payload)`. Update `_posting_to_orm`/`_posting_to_domain` for nullable descriptions. | New repo surface for fetch-details. |
| `src/jmi/cli.py:32-34` | Replace if/elif with dispatch dict `{"huggingface": HuggingFaceScraper, "jjit": JJITListScraper}`. Add `fetch-details` command with `--source`, `--limit`, `--rate`. | Two-source dispatch + new command. |
| `src/jmi/extractors/anthropic.py` | In `extract_one`, skip postings with empty/None `description_text` — log `extract.skip.no_description`, count as `skipped`. | Empty-description safety after separated pipeline. |
| `pyproject.toml` | `uv add alembic`. | §1. |
| `tests/sources/jjit/` (new), `tests/sources/jjit/fixtures/` (new) | Test scaffolding. | §11. |

### New repository methods

```python
def list_pending_details(self, source: str, limit: int = 100) -> list[JobPosting]:
    stmt = (
        select(JobPostingORM)
        .where(
            JobPostingORM.source == source,
            JobPostingORM.description_text.is_(None),
        )
        .order_by(JobPostingORM.scraped_at.asc())  # FIFO: oldest list-scrape backlog drains first
        .limit(limit)
    )
    return [_posting_to_domain(o) for o in self._session.execute(stmt).scalars()]

def update_description(self, id: UUID, html: str, text: str, raw_payload: dict) -> None:
    orm = self._session.get(JobPostingORM, id)
    if orm is None:
        raise KeyError(id)
    orm.description_html = html
    orm.description_text = text
    orm.raw_payload = raw_payload
    self._session.flush()
```

In-row UPDATE preserves the UUID — important because `job_extracts.job_posting_id` may already FK to it (extracts could in theory have run on a list-only row, though we now skip those — defensive).

---

## 10. Anti-bot / ToS

**See §0 for the robots.txt blocker.** Below assumes user decides to proceed.

### Default headers (in `JJITClient`)

```python
DEFAULT_HEADERS = {
    "User-Agent": "JMI-research-bot/0.1 (+https://github.com/<user>/jmi; contact: <email>)",
    "Accept": "application/json",
    "Accept-Language": "en;q=0.9, pl;q=0.8",
}
```

Honest UA over browser spoofing. If JJIT operations sees our traffic and wants to block, they can — and we'd rather be a contactable bot than anonymous. If the API hard-rejects non-browser UAs (verify in §7 smoke test), fall back to a real Chrome UA but keep contact info in a `From:` header per RFC 9110.

### ToS / regulamin manual checklist (before merge)

- Find the right URL — `/regulamin` 404'd in WebFetch. Try `/terms`, `/regulations`, footer links on `https://justjoin.it`.
- Search for: `crawl`, `scrap`, `bot`, `automatyzacj`, `pobieranie danych`, `roboty`, `API`, `interfejs programistyczny`. Read surrounding clauses.
- Note any "fair use" / req-per-min language.
- Look at the JJIT footer for a public/partner API — if one exists, prefer it over scraping.

**Documented stance**: personal, non-commercial job-search research at <200 detail requests/day. Code includes a kill switch (`JMI_DISABLED_SOURCES=jjit` env var or 403 → log + exit, no retry).

### Detection signals → exit, do NOT bypass

- HTTP 403 with HTML body → log `jjit.blocked.403`, raise `JJITError`, exit cleanly.
- HTTP 429 with `Retry-After > 60s` → log `jjit.throttled.long_wait`, exit (don't sleep an hour mid-run).
- Cloudflare challenge HTML (contains `cf-chl-bypass` / `__cf_chl_jschl_tk__`) → log `jjit.blocked.cloudflare`, exit. Never bypass.
- 401 / captcha → same.

If blocked: user decides to (a) wait 24h, (b) `--rate 2.0`, (c) abandon and pivot to NFJ early. Never auto-rotate UA or IP.

---

## 11. Tests

Per CLAUDE.md (`scrapers themselves not tested — flaky`): test mappers, parsers, and new repo methods. Skip the orchestration loops in `JJITListScraper.run` / `JJITDetailFetcher.run`.

### Fixtures (one-time capture, anonymized)

- `tests/sources/jjit/fixtures/offers_page.json` — `/offers?from=0&itemsCount=10` response, 10 offers, `meta` intact. Anonymize: `companyName` → synthetic, `guid` → `uuid5(NS, original)` (deterministic, stable test keys, no real listing leaks).
- `tests/sources/jjit/fixtures/offer_detail_full.json` — one full detail with rich HTML body (junior IT, Polish + English mix, salary, bullets).
- `tests/sources/jjit/fixtures/offer_detail_minimal.json` — empty body, no salary (defensive case).
- `tests/sources/jjit/fixtures/body_quill.html`, `body_quill_polish.html`, `body_msword.html`, `body_empty.html` — extracted body HTML in isolation for parser tests.

### `tests/sources/jjit/test_mapper.py`

- `test_maps_required_fields` — source/source_job_id (=guid)/url/title/company_name/scraped_at/raw_payload echoed
- `test_description_fields_are_none_after_list_only`
- `test_published_at_parses_iso8601_to_aware_utc`
- `test_published_at_missing_becomes_none`
- `test_location_from_city_and_locations_array`
- `test_company_name_comes_from_payload_not_class_constant` (multi-company contrast vs HF)
- `test_missing_guid_raises` / `test_invalid_url_raises_validation_error`

### `tests/sources/jjit/test_html_parser.py`

- `test_empty_html_returns_empty_string`
- `test_quill_paragraphs_separated_by_newline`
- `test_quill_bullets_emit_dashes` — `<ul><li>Python</li><li>Django</li></ul>` → `"- Python\n- Django"`
- `test_quill_headers_emit_markdown_h2` — `<p class="ql-header-2">Wymagania</p>` → `## Wymagania`
- `test_polish_chars_preserved` — `ą ć ę ł ń ó ś ź ż` round-trip with no mojibake
- `test_strips_html_tags`
- `test_collapses_excess_blank_lines`
- `test_msword_class_treated_as_paragraph` (defensive)
- `test_falls_back_to_get_text_when_walker_empty` (regression catch)

### `tests/sources/jjit/test_details_merge.py`

- `test_merge_writes_html_and_text`
- `test_raw_payload_preserves_list_metadata_under_detail_key`
- `test_merge_with_empty_body_returns_empty_strings`

### `tests/storage/test_jobs_repo.py` (new)

For `list_pending_details` + `update_description`. Pre-existing `tests/conftest.py` is empty; this is the right moment to add a session fixture (sqlite in-memory if it accepts the schema with a few type substitutions; otherwise testcontainers Postgres — Week 2 fixture comment in conftest.py points there).

- `test_list_pending_details_excludes_filled_rows`
- `test_list_pending_details_orders_oldest_first`
- `test_list_pending_details_filters_by_source` (don't return HF rows when called with `"jjit"`)
- `test_update_description_in_place_preserves_uuid`
- `test_update_description_persists_raw_payload_merge`

### Smoke test addition to `tests/test_smoke.py`

Assert `from jmi.sources.jjit import JJITClient, JJITListScraper, JJITDetailFetcher` works (catches import / circular-import regressions).

### What we deliberately do NOT test

- `JJITListScraper.run` pagination loop (orchestration)
- `JJITDetailFetcher.run` sleep loop (orchestration)
- `JJITClient` HTTP retry behavior (`respx` is in dev deps but we'd rather rely on the §7 smoke than fake HTTP)
- Live JJIT API integration (manual smoke per §7)

---

## 12. Verification (end-to-end)

Sequential commands after PR merges:

```bash
# 1. Bring up DB + apply migrations
docker compose up -d
uv run alembic upgrade head

# 2. List-only scrape, 100 jobs
uv run jmi scrape -s jjit -n 100
# Expected stdout: "100 new, 0 existing, 0 invalid"

# 3. Inspect what landed
psql $DATABASE_URL -c "SELECT count(*), source FROM job_postings GROUP BY source;"
# Expected: jjit | 100 (plus existing huggingface rows)

# 4. Detail fetch
uv run jmi fetch-details -s jjit -n 100 --rate 0.5
# Expected wall time: ~50-60s
# Expected stdout: "100 updated, 0 skipped_no_body, 0 invalid, 0 api_failures"

# 5. Extract
uv run jmi extract -n 100
# Expected: 100 extracted, 1 cache miss + 99 cache hits (cold cache miss on first row)
```

### Metrics queries (capture into Week 2 retro)

```sql
-- Avg description length (parser sanity)
SELECT source, avg(length(description_text))::int AS avg_chars
FROM job_postings WHERE source='jjit';
-- Expected: 800-3000 chars

-- % of postings with salary
SELECT 100.0 * sum(CASE WHEN jsonb_array_length(raw_payload->'employmentTypes')>0 THEN 1 ELSE 0 END) / count(*)
FROM job_postings WHERE source='jjit';
-- Expected: 70-90% (JJIT mandates salary disclosure but B2B has flexibility)

-- experienceLevel distribution
SELECT raw_payload->>'experienceLevel' AS lvl, count(*)
FROM job_postings WHERE source='jjit' GROUP BY 1 ORDER BY 2 DESC;

-- Top 10 categories
SELECT raw_payload->'category'->>'key' AS cat, count(*)
FROM job_postings WHERE source='jjit' GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
-- Sanity: top should be Java, JS, Python; if "Sales" dominates, wrong endpoint

-- LLM vs JJIT-raw spot-check (poor-man's eval framework preview)
SELECT
  jp.title,
  jp.raw_payload->>'experienceLevel' AS jjit_level,
  je.seniority AS llm_seniority,
  jp.raw_payload->>'workplaceType' AS jjit_workplace,
  je.remote_policy AS llm_remote
FROM job_postings jp JOIN job_extracts je ON je.job_posting_id = jp.id
WHERE jp.source='jjit' LIMIT 20;
-- Eyeball agreement; if <70% on seniority, prompt needs PL-specific examples
```

### Success criteria

- 100 list rows in DB after step 2, no errors in structured logs.
- 100 details filled after step 4, ≤5 `skipped_no_body` (slug 404s for unpublished offers), 0 `failed_api_calls`.
- 100 extracts after step 5, cache_hit ≥ 95% (one cold + 99 reads).
- Spot-check 5 random postings: `description_text` reads as cleanly-formatted text (bullets visible, no HTML noise, Polish chars intact).

---

## 13. Świadomie odłożone (consciously deferred)

- `BaseScraper` / shared abstract class — wait for rule-of-three (after NFJ Week 3).
- Cursor pagination (`meta.prev.cursor`) — offset suffices at our scale; revisit if duplicates appear in pagination.
- Category filter in list scrape (`?categories=...`) — broad coverage first, filter when dashboards need it.
- Incremental scrape (delta since last `scraped_at`) — needs scrape-watermark table; defer to daily cron (Week 5+).
- Multi-language extractor tuning (Polish-specific prompt examples) — defer to Week 3 retro after measuring extraction quality.
- Structured columns + LLM cross-check (Option B from §3) — defer to Phase 3 with eval framework.
- Fast-path skip-LLM (Option C from §3) — re-evaluate only if Anthropic costs become a documented bottleneck.
- `--force` flag on `fetch-details` — YAGNI; only if a parser bug requires re-parsing.
- `list_pending_extract` repo method — extractor's per-row skip suffices for v1.
- `JobExtractORM.tech_stack` JSON → JSONB consistency fix — separate tidy-up migration when convenient.
- Per-source SLO/alerting — logs are enough for Phase 1.
- Live JJIT integration tests in CI — manual smoke per §7 only.

---

## PR sequencing (5 PRs, ~2-3 dev sessions)

1. **PR 1 — Alembic adoption + baseline migration.** Schema bookkeeping only, no JJIT yet. Validates Alembic setup independently.
2. **PR 2 — JJIT prerequisites migration.** Migration 0002: nullable description columns + Source literal extension. Tiny PR.
3. **PR 3 — JJIT client + mapper + html_parser + tests.** Pure functions and HTTP wrapper. No DB writes from this PR. Smoke-testable in isolation per §7.
4. **PR 4 — List scraper + `jmi scrape -s jjit` + repo `update_description`.** Now writes to DB; visible in psql.
5. **PR 5 — Detail fetcher + `jmi fetch-details` + `list_pending_details` + extractor empty-description skip.** Closes the loop end-to-end.

Each <30-min review, reverts cleanly.

---

## Open uncertainties to validate empirically before / during code

1. **Public URL pattern** for an offer detail page (`/job-offer/{slug}` is a guess from the brief — verify in browser).
2. **`guid` is in the list response** (brief says yes; confirm in captured fixture).
3. **JSON `body` is HTML string vs Quill delta** (assumed HTML; verify in §7 smoke).
4. **`itemsCount` cap > 100** (use 100 default until verified).
5. **JJIT regulamin language** about scraping/automation (§0 + §10).
6. **Whether Alembic autogenerate handles UniqueConstraint + JSONB correctly** (§1 dry-run).
7. **Whether sqlite-in-memory accepts our schema for repo tests, or we need testcontainers Postgres now** (§11 — falls into Week 2 conftest plan either way).

---

## Critical files (for implementation reference)

- `src/jmi/sources/huggingface/scraper.py` — pattern for `_owns_client`, structured logging, `ScrapeStats` dataclass
- `src/jmi/sources/huggingface/client.py` — pattern for httpx + tenacity
- `src/jmi/sources/huggingface/mapper.py` — pure function `to_posting`, BeautifulSoup usage
- `src/jmi/storage/jobs.py` — repo style + `_posting_to_orm`/`_posting_to_domain` mappers
- `src/jmi/db/models.py` — ORM definitions (lines to mutate for nullable descriptions)
- `src/jmi/cli.py` — Typer commands, dispatch pattern
- `src/jmi/models/job.py` — Pydantic models (line 9 Source literal)
- `src/jmi/extractors/anthropic.py` — extractor (empty-description skip insertion point)
- `docs/adr/0006-extraction-pipeline-architecture.md` — ADR being strengthened
