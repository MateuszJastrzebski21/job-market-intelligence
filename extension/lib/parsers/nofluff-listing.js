// Parses the NoFluffJobs listing page DOM into IngestPostingIn[] for
// POST /api/ingest. Selectors inspected via Claude in Chrome MCP on
// 2026-05-15 — see docs/nofluff-selectors.md for the empirical log.
//
// HITL invariant: caller (content script) invokes this only after a user
// gesture (popup "Save jobs on this page" click). The parser is pure: no
// scrolling, no fetching, no DOM mutation.
//
// Module shape: loaded as a *classic* content script alongside
// content-scripts/nofluff.js — top-level `function` declarations land on the
// isolated-world global so nofluff.js can call `parseNFJListing` directly.
// The bottom `module.exports` block is a no-op in the browser and only
// matters for vitest (Node), which loads the file via createRequire.
//
// source_id: NFJ exposes a stable posting id on `card.id`
// (`nfjPostingListItem-{ID}`), but that id is NOT recoverable from the
// `/pl/job/{slug}` detail URL the background fetcher re-keys off. To keep the
// listing→detail round-trip consistent (mirroring JJIT), source_id is the URL
// slug; the posting id is kept in raw_payload.nfj_posting_id for audit.

function parseNFJListing(doc) {
  const errors = [];
  const lists = doc.querySelectorAll("nfj-postings-list");
  const cards = doc.querySelectorAll("a[nfj-postings-item]");
  if (cards.length === 0) {
    return {
      postings: [],
      cardCount: 0,
      errors: [
        lists.length === 0
          ? "no nfj-postings-list found — NFJ layout may have changed"
          : "nfj-postings-list present but no a[nfj-postings-item] cards — NFJ layout may have changed",
      ],
    };
  }
  const postings = [];
  cards.forEach((card, idx) => {
    try {
      const parsed = parseCard(card);
      if (parsed) postings.push(parsed);
    } catch (err) {
      errors.push(`Card ${idx}: ${err && err.message ? err.message : String(err)}`);
    }
  });
  return { postings, cardCount: cards.length, errors };
}

function parseCard(card) {
  const href = card.getAttribute("href") || "";
  const slugMatch = href.match(/^\/(?:pl|en)\/job\/([^?#]+)/);
  if (!slugMatch) {
    console.warn("[NFJ parser] card href is not a /job/ detail path, skipping", { href });
    return null;
  }
  const slug = slugMatch[1].replace(/\/+$/, "");
  if (!slug) {
    console.warn("[NFJ parser] empty slug, skipping", { href });
    return null;
  }

  // Defensive: a card without a title or company isn't a real offer (could
  // be a promo tile or a layout reshuffle). Log + skip — never crash the
  // batch over one bad card.
  const titleEl = card.querySelector('[data-cy="title position on the job offer listing"]');
  const title = titleEl ? (titleEl.textContent || "").trim() : "";
  if (!title) {
    console.warn("[NFJ parser] card has no title, skipping", { href });
    return null;
  }
  const company = textOrNull(card.querySelector("h4.company-name"));
  if (!company) {
    console.warn("[NFJ parser] card has no company, skipping", { href });
    return null;
  }

  // Salary element is absent when the salary is undisclosed → null.
  const salaryRaw = textOrNull(
    card.querySelector('[data-cy="salary ranges on the job offer listing"]'),
  );
  const locationRaw = primaryLocation(
    textOrNull(card.querySelector('[data-cy="location on the job offer listing"]')),
  );
  const techStack = Array.from(
    card.querySelectorAll('[data-cy="category name on the job offer listing"]'),
  )
    .map((el) => (el.textContent || "").trim())
    .filter(Boolean);

  const postingId = (card.id || "").replace(/^nfjPostingListItem-/, "") || null;

  return {
    source_id: slug,
    url: `https://nofluffjobs.com${href}`,
    title,
    company_name: company,
    location_raw: locationRaw,
    salary_raw: salaryRaw,
    posted_at: null, // Listing card doesn't expose posted_at; detail fetch may populate.
    raw_payload: {
      tech_stack: techStack,
      nfj_posting_id: postingId,
    },
  };
}

function textOrNull(el) {
  if (!el) return null;
  const t = (el.textContent || "").trim();
  return t.length ? t : null;
}

function primaryLocation(raw) {
  if (!raw) return null;
  // Multi-location cards render the primary city plus a "+N" overflow badge
  // ("Zdalnie +1"); the hidden popover with the other city names also lands
  // in textContent. Cut everything from the "+N" badge onward.
  const normalized = raw.replace(/\s+/g, " ").trim();
  const primary = normalized.replace(/\s*\+\s*\d+.*$/, "").trim();
  return primary.length ? primary : (normalized || null);
}

if (typeof module !== "undefined" && typeof module.exports !== "undefined") {
  module.exports = { parseNFJListing };
}
