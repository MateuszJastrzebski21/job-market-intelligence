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

/**
 * True for a NoFluffJobs URL that renders a multi-card listing page.
 *
 * Empirically verified 2026-05-15 — see docs/nofluff-selectors.md
 * "Listing URL patterns". NFJ is bilingual: listings exist under both
 * /pl/* and /en/*.
 *
 * Matches:
 *   https://nofluffjobs.com/                  ✓ root (redirects to /pl)
 *   https://nofluffjobs.com/pl                ✓ PL curated landing
 *   https://nofluffjobs.com/en                ✓ EN curated landing
 *   https://nofluffjobs.com/pl/backend        ✓ PL category job board
 *   https://nofluffjobs.com/en/devops         ✓ EN category job board
 *   https://nofluffjobs.com/pl/jobs           ✓ matches pattern (NFJ redirects to /pl)
 *
 * Excludes:
 *   https://nofluffjobs.com/pl/job/{slug}     ✗ detail page
 *   https://nofluffjobs.com/pl/company/{slug} ✗ company profile
 */
export function isNFJListingUrl(urlStr) {
  try {
    const u = new URL(urlStr);
    if (u.protocol !== "https:") return false;
    if (u.hostname !== "nofluffjobs.com") return false;
    const path = u.pathname.replace(/\/+$/, "") || "/";
    if (path === "/" || path === "/pl" || path === "/en") return true;
    const m = path.match(/^\/(pl|en)\/(.+)$/);
    if (!m) return false;
    const rest = m[2];
    if (rest === "job" || rest.startsWith("job/")) return false;
    if (rest === "company" || rest.startsWith("company/")) return false;
    return true;
  } catch {
    return false;
  }
}

/** True for any HTTPS URL whose origin is NFJ (used by Retry-button portal detection). */
export function isNFJUrl(urlStr) {
  try {
    const u = new URL(urlStr);
    return u.protocol === "https:" && u.hostname === "nofluffjobs.com";
  } catch {
    return false;
  }
}
