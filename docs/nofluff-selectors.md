# NoFluffJobs Listing Page — DOM Selectors

**Source URL:** `https://nofluffjobs.com/` redirects to `https://nofluffjobs.com/pl`
(Polish locale; EN at `/en`). The bare `/pl` homepage is a **curated landing
page** (offers-of-the-day + curated sections, ~28 cards, no pagination). The
browsable job board lives at **category paths** — e.g.
`https://nofluffjobs.com/pl/backend`. `/pl/jobs` redirects back to `/pl`.

**Last verified:** 2026-05-15 (NFJ scraper prep, via Claude in Chrome MCP DOM probe).

**Re-validate:** every 4-6 weeks, or whenever the parser produces 0 cards /
wrong fields. NFJ is an Angular app — it churns `ng-*` and Tailwind `tw-*`
class names on upgrades; DO NOT depend on those. NFJ DOES expose `data-cy`
(Cypress) attributes and Angular component tag/attribute names (`nfj-*`) —
prefer those.

## Stable anchors (use these)

| Role | Selector | Source of stability |
|---|---|---|
| List section | `nfj-postings-list[data-cy="nfjPostingsList"]` | Angular component + data-cy |
| Card container | `div.list-container` (inside a list section) | semantic class |
| Card (one offer) | `a[nfj-postings-item]` | Angular component attribute selector |
| Detail URL | `card.getAttribute('href')` → `/pl/job/{slug}` | relative href |
| Posting ID | `card.id` → `nfjPostingListItem-{ID}` | stable NFJ posting id (e.g. `XOEYPPK5`) |

## Per-field extraction (listing card)

NFJ exposes descriptive `data-cy` attributes inside each card — use them as the
primary selectors.

| Field | Selector (within card) | Notes |
|---|---|---|
| Title | `[data-cy="title position on the job offer listing"]` | `<h3>`, also `.posting-title__position` |
| Company | `h4.company-name` | no data-cy |
| Salary | `[data-cy="salary ranges on the job offer listing"]` | `<span.posting-tag>`; element absent when salary undisclosed; e.g. `21 840 – 24 360 PLN` |
| Tech tags | `[data-cy="category name on the job offer listing"]` | `<span.posting-tag>`, multiple per card |
| Location | `[data-cy="location on the job offer listing"]` | `<nfj-posting-item-city>`; multi-location rendered as "Zdalnie +1" with a `popover-locations` popover |
| New badge | `<span>` containing text `NOWA` | optional |
| Favorite btn | `[data-cy="job favourite btn listing"]` | ignore for extraction |

## `source_job_id` derivation

The card carries the NFJ posting id directly in its `id` attribute:

```js
const sourceJobId = card.id.replace(/^nfjPostingListItem-/, "");  // e.g. "XOEYPPK5"
```

This is more stable than the URL slug (slugs can be re-published with a `-{n}`
suffix). Fallback: the slug from `href` (`/pl/job/{slug}`).

## Pagination — user-driven "load more"

A category listing loads an initial batch (~20 cards spread over
`nfj-postings-list` sections) and appends more when the user clicks the
**"Pokaż kolejne oferty"** button:

`button.tw-btn.tw-btn-primary.tw-btn-xl` — no `data-cy`; match by text
`/Pokaż kolejne oferty/i`.

It is NOT infinite scroll and NOT numbered pagination. HITL implication
(ADR-0009): the user clicks "load more" until the cards they want are revealed,
then saves the page; the extension MUST NOT auto-click it — every save batch is
exactly what the user has already viewed.

## Resilience strategy

- Primary anchors: `a[nfj-postings-item]` plus the `data-cy` attributes. If
  `a[nfj-postings-item]` disappears, the parser returns `cardCount=0` with a
  diagnostic error.
- Never depend on `ng-*`, `tw-*`, or `_ngcontent-*` attributes — they churn.
- The URL matcher accepts both `/pl/*` and `/en/*` paths; the detail parser
  keys off section IDs (locale-independent), so it works on either locale.

---

# NoFluffJobs Detail Page — DOM Selectors

**Source URL pattern:** `https://nofluffjobs.com/pl/job/{slug}` — slug = title +
company + location keywords, with an optional `-{n}` suffix disambiguating
duplicates (e.g. `/pl/job/data-scientist-link-group-remote-7`).

**Last verified:** 2026-05-15 (via Claude in Chrome MCP DOM probe).

**Rendering:** Angular app with Angular Universal SSR (DOM carries
`_ngcontent-serverapp-*` attributes). A raw `fetch()` from the extension
service worker likely returns server-rendered HTML — verify with a byte-count +
content check before relying on it (see verification commands). No schema.org
JSON-LD is embedded.

## Description extraction strategy

Detail content is split into `<section>` blocks with stable, **locale-independent
`id`s**. The description prose is plain HTML (`<p><span>` …) — there is **no
Quill `.ql-editor`** container.

| Section | Selector | PL heading |
|---|---|---|
| Job description | `section#posting-description` | "Opis oferty" |
| Responsibilities | `section#posting-tasks` | "Zakres obowiązków" |
| Nice-to-have tech | `section#posting-nice-to-have` | "Mile widziane" |
| Offer details | `section#posting-specs` | "Szczegóły oferty" (recruitment mode, start date, remote) |
| Must-have tech + languages | `<section>` (no id) under `<h2>` "Obowiązkowe" | "Obowiązkowe" |
| Requirements | `<section>` (no id) under `<h2>` "Opis wymagań" | "Opis wymagań" |

Each section nests inside:
`div.col-lg-8.mobile-no-padding > common-posting-content-wrapper > div.mb-20 > section`.

For the LLM extractor's `description_text`, concatenate the text of
`#posting-description`, `#posting-tasks`, the requirements section, and the
must-have / nice-to-have tech sections. Key the parser off the section **`id`s**
(locale-independent), not heading text. The two sections without `id`s
("Obowiązkowe", "Opis wymagań") are reached via their `<h2>` heading text.

## Detail header fields

| Field | Selector |
|---|---|
| Title | `h1` |
| Company | `a[data-cy="JobOffer_CompanyProfile"]` (text = company name; href `/pl/company/{slug}-{id}`) |
| Salary | `h4` (desktop) / `[data-cy="JobOffer_SalaryDetails_Mobile"]` (mobile) |
| Category | `a[data-cy="JobOffer_Category"]` |

## Bilingual handling

NFJ serves PL at `/pl/...` and EN at `/en/...`. Each content section contains a
`common-posting-translate-section` element — NFJ's machine-translation toggle
(empty/inactive for postings authored in the page's locale). Because the
section **`id`s are locale-independent**, the parser does not need EN heading
text — target `section#posting-*` directly. (EN job slugs differ from PL slugs;
`/en/job/{pl-slug}` does not resolve to the detail page.)

## Verification commands (DevTools Console on a `/pl/job/{slug}` page)

```js
// 1. description section present + content length
const d = document.querySelector("section#posting-description");
console.log({ found: !!d, len: d?.textContent.trim().length });
// → expect { found: true, len: 100-4000 }

// 2. does a raw fetch return SSR HTML (description present in raw response)?
fetch(location.href, { credentials: "include" })
  .then(r => r.text())
  .then(t => console.log({ bytes: t.length, hasDesc: t.includes("posting-description") }));
```

---

# Listing URL patterns

**Last verified:** 2026-05-15.

NFJ is bilingual: every listing/detail surface exists under both a `/pl/*`
(Polish) and an `/en/*` (English) path. The URL matcher must accept both.

| URL | Role |
|---|---|
| `https://nofluffjobs.com/` | redirects to `/pl` |
| `https://nofluffjobs.com/pl` | PL curated landing page (offers of the day) — limited card set, no pagination |
| `https://nofluffjobs.com/en` | EN curated landing page — EN equivalent of `/pl` |
| `https://nofluffjobs.com/pl/{category}` (e.g. `/pl/backend`) | PL category job board — real listing, "Pokaż kolejne oferty" pagination |
| `https://nofluffjobs.com/en/{category}` (e.g. `/en/backend`) | EN category job board — EN equivalent |
| `https://nofluffjobs.com/pl/job/{slug}` | PL detail page — NOT a listing |
| `https://nofluffjobs.com/en/job/{slug}` | EN detail page — NOT a listing (EN slug differs from the PL slug) |
| `https://nofluffjobs.com/pl/jobs` | redirects to `/pl` — not a listing path |

**NOT yet captured:** the filter / location / experience / salary URL shapes
produced by the on-page "Filtry / Lokalizacja / Doświadczenie / Wynagrodzenie"
controls. Capture these during PR15 when building the popup URL-matcher
(`isNFJListingUrl`), the same way the JJIT matcher was built — see the
"Listing URL patterns" section of `docs/jjit-selectors.md`.

## Cookie consent

First visit shows a Usercentrics consent banner ("Pozwól na cookies…").
Dismiss via "Zapisz ustawienia" (saves with only strictly-necessary cookies).
Not relevant to the parser; noted for manual re-inspection sessions.
