// JMI Job Saver — background service worker (Manifest V3, ES module).
// PR4 skeleton: message router with three actions. HEALTH_CHECK is wired up;
// INGEST_LISTING / INGEST_DETAILS return stub responses that PR5 (JJIT
// content script) and PR6 (detail fetcher) will replace with real logic.

import { JmiClient, readSettings } from "../lib/jmi-client.js";

console.log("[JMI SW] booted");

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

        case "INGEST_LISTING":
          // PR5 (JJIT) and PR7 (NFJ) replace this stub with the real flow:
          // receive parsed cards from content script, POST /api/ingest,
          // store stats in chrome.storage.local, kick off INGEST_DETAILS.
          console.log("[JMI SW] INGEST_LISTING stub", message);
          sendResponse({
            ok: false,
            error: "INGEST_LISTING not implemented yet (PR5).",
          });
          return;

        case "INGEST_DETAILS":
          // PR6 replaces this stub with the rate-limited detail fetch loop
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
