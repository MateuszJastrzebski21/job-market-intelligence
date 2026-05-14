// JMI Job Saver — background service worker (Manifest V3, ES module).
// Message router for HEALTH_CHECK, INGEST_LISTING, and INGEST_DETAILS.
// HEALTH_CHECK + INGEST_LISTING are wired in PR4/PR5; INGEST_DETAILS is a
// stub that PR6 (background detail fetcher) will replace.

import { JmiClient, readSettings } from "../lib/jmi-client.js";

console.log("[JMI SW] booted");

const ERRORS_BUFFER_MAX = 50;

async function appendError({ action, source, reason }) {
  const { errors = [] } = await chrome.storage.local.get("errors");
  errors.push({
    ts: new Date().toISOString(),
    action: action || "(unknown)",
    source: source || null,
    reason: reason || "(no reason)",
  });
  await chrome.storage.local.set({ errors: errors.slice(-ERRORS_BUFFER_MAX) });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      switch (message?.action) {
        case "HEALTH_CHECK": {
          const settings = await readSettings();
          if (!settings.baseUrl) {
            sendResponse({
              ok: false,
              error: "JMI URL not configured. Open extension Settings.",
            });
            return;
          }
          const client = new JmiClient(settings.baseUrl, settings.token);
          try {
            const health = await client.health();
            sendResponse({ ok: true, health });
          } catch (err) {
            sendResponse({ ok: false, error: String(err?.message || err) });
          }
          return;
        }

        case "INGEST_LISTING": {
          const settings = await readSettings();
          if (!settings.baseUrl || !settings.token) {
            sendResponse({
              ok: false,
              error: "JMI URL or ingest token not configured. Open Settings.",
            });
            return;
          }
          if (!message.source || !Array.isArray(message.postings)) {
            sendResponse({ ok: false, error: "Bad INGEST_LISTING payload" });
            return;
          }
          if (message.postings.length === 0) {
            sendResponse({
              ok: true,
              accepted: 0,
              skipped_existing: 0,
              invalid: [],
            });
            return;
          }
          const client = new JmiClient(settings.baseUrl, settings.token);
          try {
            const result = await client.ingest(message.source, message.postings);
            await chrome.storage.local.set({
              lastSave: {
                ts: new Date().toISOString(),
                count: result?.accepted || 0,
                source: message.source,
              },
            });
            sendResponse({
              ok: true,
              accepted: result?.accepted || 0,
              skipped_existing: result?.skipped_existing || 0,
              invalid: result?.invalid || [],
            });
          } catch (err) {
            await appendError({
              action: "INGEST_LISTING",
              source: message.source,
              reason: String(err?.message || err),
            });
            sendResponse({ ok: false, error: String(err?.message || err) });
          }
          return;
        }

        case "INGEST_DETAILS":
          // PR6 replaces this stub with the rate-limited detail-fetch loop
          // (offscreen-document DOMParser + batch POST /api/details).
          console.log("[JMI SW] INGEST_DETAILS stub", message);
          sendResponse({
            ok: false,
            error: "INGEST_DETAILS not implemented yet (PR6).",
          });
          return;

        default:
          sendResponse({
            ok: false,
            error: `Unknown action: ${message?.action}`,
          });
      }
    } catch (err) {
      console.error("[JMI SW] handler error", err);
      sendResponse({ ok: false, error: String(err?.message || err) });
    }
  })();

  // Returning true keeps sendResponse alive for the async block above.
  return true;
});
