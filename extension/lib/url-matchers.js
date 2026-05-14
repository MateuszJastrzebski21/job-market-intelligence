// Per-portal URL matchers used by the popup to decide:
//   - whether the active tab IS a job-listing page (Save button enable)
//   - whether a previously-failed URL belongs to a known portal (Retry button)
//
// Pure functions, ESM. Tested in extension/tests/url-matchers.test.js.
// PR7 (NoFluffJobs) and PR8 (LinkedIn) will append their own matchers here.

/**
 * True for a JJIT URL that renders a multi-card listing page.
 *
 * Empirically verified 2026-05-15 — see docs/jjit-selectors.md
 * "Listing URL patterns".
 *
 * Matches:
 *   https://justjoin.it/                                ✓ root
 *   https://justjoin.it/?with-salary=yes                ✓ root + query filter
 *   https://justjoin.it/job-offers/all-locations/ai     ✓ category filter
 *   https://justjoin.it/job-offers/warszawa             ✓ location filter
 *   https://justjoin.it/job-offers/krakow/python        ✓ location + category
 *
 * Excludes:
 *   https://justjoin.it/job-offer/{slug}                ✗ singular = detail page
 *   https://justjoin.it/regulamin                       ✗ static page
 *   https://justjoin.it/admin/                          ✗ unrelated
 *   https://justjoin.it/job-offers                      ✗ no trailing slash (JJIT
 *                                                         always serves trailing)
 */
export function isJJITListingUrl(urlStr) {
  try {
    const u = new URL(urlStr);
    if (u.protocol !== "https:") return false;
    if (u.hostname !== "justjoin.it") return false;
    return u.pathname === "/" || u.pathname.startsWith("/job-offers/");
  } catch {
    return false;
  }
}

/** True for any HTTPS URL whose origin is JJIT (used by Retry-button portal detection). */
export function isJJITUrl(urlStr) {
  try {
    const u = new URL(urlStr);
    return u.protocol === "https:" && u.hostname === "justjoin.it";
  } catch {
    return false;
  }
}
