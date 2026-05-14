# JJIT Listing Page — DOM Selectors

**Source URL:** `https://justjoin.it/` (root). The path `/all-offers` returns 404 — the listing lives at the root, not at a dedicated path.

**Last verified:** 2026-05-14 (PR5, via Claude in Chrome MCP DOM probe).

**Re-validate:** every 4-6 weeks, or whenever the parser starts producing 0 cards / wrong fields. JJIT uses Material UI with minified `mui-XXXXX` class names that churn on library upgrades — DO NOT depend on those.

## Stable anchors (use these)

| Role | Selector | Source of stability |
|---|---|---|
| Container | `#up-offers-list` | Stable HTML `id` on the wrapper `<div>` |
| Card (one offer) | `a.offer-card` | Semantic class name, not minified |
| Detail URL | `card.getAttribute('href')` | Returns `/job-offer/{slug}` |
| Title | `card.querySelector('h3')` | Semantic heading, one per card |

## Per-field extraction (positional, by content-type discriminator)

JJIT has **zero** `data-testid` / `data-test` / `aria-label` / `role` attributes inside cards. We're stuck with semantic + positional selection. Each "logical" field is rendered twice (visible + screen-reader duplicate for a11y); always take the first occurrence in document order.

| Field | Strategy |
|---|---|
| Company | First `<p>` inside the card |
| Location | Second `<p>` (e.g. `"Warszawa"` or `"Krakow, +2 Locations"`) |
| Workplace type | Third `<p>` (`"Remote"` / `"Hybrid"` / `"Onsite"`) |
| Salary range | First `<span>` whose text matches `/\d/` AND contains `-` |
| Salary unit | The `<span>` immediately following the salary range |
| Seniority label | First `<span>` whose text is in `{"Junior", "Mid", "Senior", "Expert"}` |
| Working time | First `<span>` whose text is in `{"Permanent", "B2B", "Mandate", "Internship"}` |
| Tech tags | Leaf `<div>`s grouped by parent where ALL of `parent.children` are leaf-text divs (excludes "Expires tomorrow" badge — its parent has an icon sibling) |

## `source_id` derivation

JJIT does **not** expose its `guid` (UUID) in the listing DOM — only on the API (which is regulamin-prohibited per ADR-0008). We derive `source_id` from the URL slug:

```js
const slug = card.getAttribute("href").replace(/^\/job-offer\//, "").replace(/\/+$/, "");
```

The slug includes company + role + location keywords and is unique per offer. JJIT may rotate slugs over time (re-publish under a new slug), but for our (`source`, `source_job_id`) idempotency this is acceptable — re-published offers will land as new rows. Slugs fit `String(256)` per the PR2 schema (longest observed ~140 chars; Polish-character role names can push close to 200).

## Verification commands (paste into DevTools Console on `https://justjoin.it/`)

```js
// 1. Container exists?
document.querySelector("#up-offers-list")
// → <div id="up-offers-list">…</div>

// 2. How many cards are currently in DOM (virtualized — only the visible window)?
document.querySelectorAll("#up-offers-list a.offer-card").length
// → typically 7-12 depending on viewport size

// 3. First card sample
const card = document.querySelector("a.offer-card");
const title = card.querySelector("h3")?.textContent.trim();
const company = card.querySelector("p")?.textContent.trim();
const slug = card.getAttribute("href").replace(/^\/job-offer\//, "");
console.log({ title, company, slug });
```

## Virtualized scroll — critical UX note

JJIT uses Virtuoso (or similar) for virtualized scrolling. Cards outside the viewport are **not** in the DOM. Implication for the extension:

1. The user must scroll through every card they want saved **before** clicking "Save jobs on this page".
2. The popup button label / tooltip should remind the user of this.
3. Auto-scrolling from the extension is **forbidden** by the HITL invariant (ADR-0009) — every save batch is exactly what the user has already viewed.

There is no built-in "load more" button — virtualized scroll is the only loading mechanism, and it's user-driven.

## Resilience strategy

- **Primary failure mode**: JJIT redesigns the card layout. The `#up-offers-list` ID and `class="offer-card"` are the only "intentional" anchors; if either disappears, the parser returns `cardCount=0` with a diagnostic error.
- **Secondary failure mode**: positional `<p>` / `<span>` order changes (e.g. company moved after city). Detection: parsed company name doesn't look like a company. Mitigation: re-inspect with the verification commands above and update positional indices.
- **Test coverage**: `extension/__tests__/jjit-listing.test.js` runs against synthetic fixtures shaped like the real DOM. Tests don't catch JJIT-side changes — they catch our own parser regressions. Real-world breakage is detected by the user noticing 0 saved jobs after a click.
