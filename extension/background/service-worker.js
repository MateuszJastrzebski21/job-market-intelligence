// JMI Job Saver — background service worker (Manifest V3, ES module).
// Message router for HEALTH_CHECK, INGEST_LISTING, INGEST_DETAILS.
// Messages targeted at the offscreen document (target: "offscreen") are
// ignored here so they reach the offscreen listener without double-handling.

import { JmiClient, readSettings } from "../lib/jmi-client.js";
import { DetailFetcher } from "./detail-fetcher.js";

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
  // Skip messages addressed to the offscreen document.
  if (message?.target === "offscreen") return undefined;

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
              accepted_indices: [],
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
              accepted_indices: result?.accepted_indices || [],
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

        case "INGEST_DETAILS": {
          const settings = await readSettings();
          if (!settings.baseUrl || !settings.token) {
            sendResponse({
              ok: false,
              error: "JMI URL or ingest token not configured. Open Settings.",
            });
            return;
          }
          if (!message.source || !Array.isArray(message.urls)) {
            sendResponse({ ok: false, error: "Bad INGEST_DETAILS payload" });
            return;
          }
          if (message.urls.length === 0) {
            sendResponse({ ok: true, updated: 0, skipped_unknown: 0, failed: 0, errors_count: 0 });
            return;
          }
          const client = new JmiClient(settings.baseUrl, settings.token);
          const fetcher = new DetailFetcher({ client, source: message.source });
          try {
            const result = await fetcher.fetchAll(message.urls);
            sendResponse({ ok: true, ...result });
          } catch (err) {
            await appendError({
              action: "INGEST_DETAILS",
              source: message.source,
              reason: String(err?.message || err),
            });
            sendResponse({ ok: false, error: String(err?.message || err) });
          }
          return;
        }

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
