// Background detail fetcher — orchestrates the per-URL fetch + offscreen
// parse + batch POST /api/details flow that closes the JJIT loop after
// /api/ingest accepts new postings.
//
// HITL invariant: the URLs passed in here came from a user-initiated save
// (popup → INGEST_LISTING → INGEST_DETAILS). The fetcher does not paginate,
// poll, or speculatively fetch anything. fetch() runs in the SW with the
// user's browser session (credentials: "include").

import { RateLimitedQueue } from "../lib/rate-limiter.js";

const OFFSCREEN_URL = "background/offscreen.html";
const DETAILS_BATCH_SIZE = 25;
const DETAILS_FLUSH_MS = 5000;

export class DetailFetcher {
  constructor({ client, source, queue } = {}) {
    if (!client) throw new Error("DetailFetcher: client required");
    if (!source) throw new Error("DetailFetcher: source required");
    this._client = client;
    this._source = source;
    this._queue = queue || new RateLimitedQueue({ minGapMs: 500, maxConcurrent: 25 });
  }

  async fetchAll(urls) {
    if (!Array.isArray(urls) || urls.length === 0) {
      return { updated: 0, skipped_unknown: 0, failed: 0, errors_count: 0 };
    }
    await this._ensureOffscreen();
    const buffer = [];
    let updated = 0;
    let skipped_unknown = 0;
    let failed = 0;
    const errors = [];
    let lastFlushMs = Date.now();

    const flush = async () => {
      if (buffer.length === 0) return;
      const batch = buffer.splice(0, buffer.length);
      try {
        const result = await this._client.details(this._source, batch);
        updated += result?.updated || 0;
        skipped_unknown += result?.skipped_unknown || 0;
        for (const inv of result?.invalid || []) {
          errors.push({ kind: "details_invalid", ...inv });
        }
      } catch (err) {
        failed += batch.length;
        errors.push({ kind: "details_post_failed", reason: errString(err) });
      }
      lastFlushMs = Date.now();
    };

    const tasks = urls.map((url) =>
      this._queue.add(async () => {
        try {
          const sourceId = extractSlug(url, this._source);
          if (!sourceId) {
            failed += 1;
            errors.push({ kind: "bad_url", url, reason: "could not extract slug" });
            return;
          }
          const html = await fetchHtml(url);
          const parsed = await parseInOffscreen({ source: this._source, html, url });
          if (!parsed?.ok) {
            failed += 1;
            errors.push({ kind: "parse_failed", url, reason: parsed?.error || "unknown" });
            return;
          }
          buffer.push({
            source_id: sourceId,
            description_html: parsed.description_html,
            description_text: parsed.description_text,
            raw_payload_patch: parsed.raw_payload_patch || {},
          });
          if (buffer.length >= DETAILS_BATCH_SIZE || Date.now() - lastFlushMs >= DETAILS_FLUSH_MS) {
            await flush();
          }
        } catch (err) {
          failed += 1;
          errors.push({ kind: "fetch_failed", url, reason: errString(err) });
        }
      }),
    );
    await Promise.all(tasks);
    await flush();
    await this._closeOffscreen();
    if (errors.length) await persistErrors(errors, this._source);

    return { updated, skipped_unknown, failed, errors_count: errors.length };
  }

  async _ensureOffscreen() {
    try {
      if (typeof chrome.offscreen?.hasDocument === "function") {
        const has = await chrome.offscreen.hasDocument();
        if (has) return;
      }
    } catch {
      // hasDocument may not exist on older Chrome; fall through to create.
    }
    try {
      await chrome.offscreen.createDocument({
        url: OFFSCREEN_URL,
        reasons: ["DOM_PARSER"],
        justification: "Parse fetched job-posting HTML to extract description.",
      });
    } catch (err) {
      // Race: another caller created it between hasDocument() and createDocument().
      // Chrome surfaces this as "Only a single offscreen document may be created."
      if (!/already|single offscreen/i.test(errString(err))) throw err;
    }
  }

  async _closeOffscreen() {
    try {
      await chrome.offscreen.closeDocument();
    } catch {
      // Already closed or not created — ignore.
    }
  }
}

// Derives source_id from a detail-page URL. Each portal keys its postings off
// a different URL shape, so the pattern is source-aware:
//   jjit    → /job-offer/{slug}
//   nofluff → /{pl|en}/job/{slug}
// The result must match the source_id the listing parser stored (both parsers
// use the URL slug).
export function extractSlug(url, source) {
  const pattern =
    source === "nofluff" ? /\/(?:pl|en)\/job\/([^?#]+)/ : /\/job-offer\/([^?#]+)/;
  const match = String(url || "").match(pattern);
  return match ? match[1].replace(/\/+$/, "") : null;
}

async function fetchHtml(url) {
  const response = await fetch(url, { credentials: "include" });
  if (response.status === 429) {
    // Single retry with 5s pause per ADR-0009 §5; on second 429 we surface
    // the failure and let the user decide via "Retry failed details" later.
    await new Promise((r) => setTimeout(r, 5000));
    const retry = await fetch(url, { credentials: "include" });
    if (!retry.ok) throw new Error(`HTTP ${retry.status} after 429 retry`);
    return retry.text();
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.text();
}

function parseInOffscreen({ source, html, url }) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      { target: "offscreen", action: "PARSE_DETAIL", source, html, url },
      (reply) => {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
          return;
        }
        resolve(reply || { ok: false, error: "empty offscreen reply" });
      },
    );
  });
}

async function persistErrors(errors, source) {
  const { errors: existing = [] } = await chrome.storage.local.get("errors");
  const stamped = errors.map((e) => ({
    ts: new Date().toISOString(),
    action: "INGEST_DETAILS",
    source,
    ...e,
  }));
  await chrome.storage.local.set({ errors: [...existing, ...stamped].slice(-50) });
}

function errString(err) {
  return String(err?.message || err || "(unknown)");
}
