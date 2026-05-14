// Parses the JJIT listing page DOM into IngestPostingIn[] for POST /api/ingest.
// Inspected via Claude in Chrome MCP on 2026-05-14 — see docs/jjit-selectors.md
// for the empirical selector log + verification commands.
//
// HITL invariant: caller (content script) invokes this only after a user gesture
// (popup "Save jobs on this page" click). The parser is pure: no scrolling, no
// fetching, no DOM mutation.
//
// Module shape: this file is loaded as a *classic* content script alongside
// content-scripts/jjit.js (MV3 doesn't reliably support ES module content
// scripts as of 2026). Top-level `function` declarations land on the isolated-
// world global, so jjit.js can call `parseJJITListing` directly. The bottom
// `module.exports` block is a no-op in the browser and only matters for vitest
// (Node) which loads the file via createRequire.

const SENIORITY_TERMS = new Set(["Junior", "Mid", "Senior", "Expert"]);
const WORKING_TIME_TERMS = new Set(["Permanent", "B2B", "Mandate", "Internship"]);

function parseJJITListing(doc) {
  const errors = [];
  const container = doc.querySelector("#up-offers-list");
  if (!container) {
    return {
      postings: [],
      cardCount: 0,
      errors: ["#up-offers-list not found — JJIT layout may have changed"],
    };
  }
  const cards = container.querySelectorAll("a.offer-card");
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
  if (!href.startsWith("/job-offer/")) {
    throw new Error(`unexpected href: ${href}`);
  }
  const slug = href.replace(/^\/job-offer\//, "").replace(/\/+$/, "");
  if (!slug) throw new Error("empty slug");

  // Defensive: a card without an <h3> isn't a real offer (could be a promo
  // tile, ad placeholder, or a layout reshuffle on JJIT's side). Log to
  // console + skip — never crash the batch over one bad card.
  const titleEl = card.querySelector("h3");
  if (!titleEl) {
    console.warn("[JJIT parser] card has no <h3> title, skipping", { href });
    return null;
  }
  const title = titleEl.textContent.trim();
  if (!title) {
    console.warn("[JJIT parser] empty title, skipping", { href });
    return null;
  }

  // <p> tags inside the card appear in document order: company, city,
  // workplace type. JJIT renders the workplace type twice (visible + a
  // screen-reader duplicate) for accessibility — ps[2] and ps[3] are the
  // same string. Taking ps[0]/ps[1] gives the canonical first occurrence
  // per logical field; we don't currently surface workplace_type as a
  // top-level field (it lives inside raw_payload via seniority/working
  // time labels picked by content match below).
  const ps = card.querySelectorAll("p");
  const company = textOrNull(ps[0]) || "(unknown)";
  const locationRaw = textOrNull(ps[1]);

  // <span> tags hold (in document order): salary range, salary unit,
  // seniority, working time. Each is rendered twice for the same a11y
  // reason as the <p> tags. Selecting by content (digits-with-dash for
  // salary, set-membership for seniority/working time) sidesteps the
  // duplication AND survives JJIT re-ordering its span layout.
  const spans = card.querySelectorAll("span");
  const salaryRaw = composeSalary(spans);

  return {
    source_id: slug,
    url: `https://justjoin.it${href}`,
    title,
    company_name: company,
    location_raw: locationRaw,
    salary_raw: salaryRaw,
    posted_at: null, // Listing card doesn't expose posted_at; PR6 detail fetch will populate.
    raw_payload: {
      tech_stack: extractTechTags(card),
      seniority_label: pickByMembership(spans, SENIORITY_TERMS),
      working_time_label: pickByMembership(spans, WORKING_TIME_TERMS),
    },
  };
}

function textOrNull(el) {
  if (!el) return null;
  const t = (el.textContent || "").trim();
  return t.length ? t : null;
}

function composeSalary(spans) {
  // First span containing digits AND a dash is the range; the next span
  // (if any) is the unit suffix like "PLN/month".
  for (let i = 0; i < spans.length - 1; i++) {
    const range = (spans[i].textContent || "").trim();
    if (/\d/.test(range) && range.includes("-")) {
      const unit = (spans[i + 1].textContent || "").trim();
      return unit ? `${range} ${unit}` : range;
    }
  }
  return null;
}

function pickByMembership(spans, terms) {
  for (const span of spans) {
    const t = (span.textContent || "").trim();
    if (terms.has(t)) return t;
  }
  return null;
}

function extractTechTags(card) {
  // Tech tags appear as a row of leaf <div>s grouped under a single parent
  // that contains ONLY tag children. Badge containers (e.g. "Expires
  // tomorrow") have a non-leaf sibling (an <svg> icon), so their parent's
  // children include mixed types — we discriminate by requiring all of
  // parent.children to be leaf-text divs.
  const groups = new Map();
  card.querySelectorAll("div").forEach((div) => {
    if (div.children.length !== 0) return;
    const text = (div.textContent || "").trim();
    if (!text) return;
    const parent = div.parentElement;
    if (!parent) return;
    if (!groups.has(parent)) groups.set(parent, []);
    groups.get(parent).push(div);
  });
  let best = [];
  for (const [parent, divs] of groups) {
    if (divs.length < 2) continue;
    if (divs.length !== parent.children.length) continue; // mixed siblings → not the tag row
    if (divs.length > best.length) best = divs;
  }
  return best.map((d) => (d.textContent || "").trim()).filter(Boolean);
}

if (typeof module !== "undefined" && typeof module.exports !== "undefined") {
  module.exports = { parseJJITListing };
}
