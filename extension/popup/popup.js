// Popup script — runs each time the popup opens.
//
// Responsibilities:
//   - Poll /api/health via the SW and paint the status pill
//   - Surface last save + recent errors from chrome.storage.local
//   - Detect the active tab's portal, enable the Save button accordingly
//   - On Save click: request portal host permission (HITL user gesture),
//     ask the content script to PARSE_LISTING, forward the result to the
//     SW for INGEST_LISTING, then auto-trigger INGEST_DETAILS for the
//     accepted URLs (PR6)
//   - Wire "Retry failed details" to re-run INGEST_DETAILS on URLs that
//     failed in a previous batch (errors persisted in chrome.storage.local)

import {
  isJJITListingUrl,
  isJJITUrl,
  isNFJListingUrl,
  isNFJUrl,
} from "../lib/url-matchers.js";

const statusEl = document.getElementById("status");
const lastSaveEl = document.getElementById("last-save");
const errorsCountEl = document.getElementById("errors-count");
const errorsListEl = document.getElementById("errors-list");
const openOptionsLink = document.getElementById("open-options");
const saveBtn = document.getElementById("save-btn");
const retryBtn = document.getElementById("retry-btn");

// Per-portal config. URL matchers live in lib/url-matchers.js so they can be
// unit-tested under jsdom without spinning up the popup. PR8 (LinkedIn) will
// append an entry here + matchers there.
const PORTALS = [
  {
    source: "jjit",
    label: "Just Join IT",
    origin: "https://justjoin.it/*",
    isListingUrl: isJJITListingUrl,
    matchesUrl: isJJITUrl,
  },
  {
    source: "nofluff",
    label: "NoFluffJobs",
    origin: "https://nofluffjobs.com/*",
    isListingUrl: isNFJListingUrl,
    matchesUrl: isNFJUrl,
  },
];

function setStatus(label, kind) {
  statusEl.textContent = label;
  statusEl.classList.remove("pill-ok", "pill-err", "pill-unknown");
  statusEl.classList.add(`pill-${kind}`);
}

async function pollHealth() {
  setStatus("checking…", "unknown");
  try {
    const reply = await chrome.runtime.sendMessage({ action: "HEALTH_CHECK" });
    if (reply?.ok && reply.health?.db_ok) {
      setStatus(`connected (v${reply.health.version})`, "ok");
    } else if (reply?.ok && reply.health) {
      setStatus("connected, DB down", "err");
    } else {
      setStatus(reply?.error || "unreachable", "err");
    }
  } catch (err) {
    console.error("[popup] HEALTH_CHECK failed", err);
    setStatus("unreachable", "err");
  }
}

async function refreshLastSave() {
  const { lastSave } = await chrome.storage.local.get("lastSave");
  if (!lastSave) {
    lastSaveEl.textContent = "none yet";
    return;
  }
  const when = new Date(lastSave.ts).toLocaleString();
  lastSaveEl.textContent = `${lastSave.count} from ${lastSave.source} at ${when}`;
}

async function refreshErrors() {
  const { errors = [] } = await chrome.storage.local.get("errors");
  errorsCountEl.textContent = String(errors.length);
  errorsListEl.innerHTML = "";
  for (const entry of errors.slice(-3).reverse()) {
    const li = document.createElement("li");
    const ts = entry.ts ? new Date(entry.ts).toLocaleTimeString() : "";
    li.textContent = `${ts} ${entry.action || ""}: ${entry.reason || entry.kind || ""}`.trim();
    errorsListEl.appendChild(li);
  }
}

async function detectPortal() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url || tab.id === undefined) return null;
  for (const portal of PORTALS) {
    if (portal.isListingUrl(tab.url)) {
      return { portal, tabId: tab.id };
    }
  }
  return null;
}

async function refreshSaveButton() {
  const detected = await detectPortal();
  if (!detected) {
    saveBtn.disabled = true;
    saveBtn.title =
      "Open a supported job-listing page (e.g. https://justjoin.it/) to enable saving.";
    return;
  }
  saveBtn.disabled = false;
  saveBtn.title = `Save jobs visible on ${detected.portal.label}`;
}

async function refreshRetryButton() {
  const failed = await collectFailedDetailUrls();
  retryBtn.disabled = failed.length === 0;
  retryBtn.title = failed.length === 0
    ? "No failed detail fetches to retry."
    : `Retry ${failed.length} failed detail fetches.`;
}

async function collectFailedDetailUrls() {
  const { errors = [] } = await chrome.storage.local.get("errors");
  const seen = new Set();
  const out = [];
  for (const entry of errors) {
    if (entry.action !== "INGEST_DETAILS") continue;
    if (!entry.url) continue;
    if (seen.has(entry.url)) continue;
    seen.add(entry.url);
    out.push(entry.url);
  }
  return out;
}

async function triggerDetailsForUrls(source, urls) {
  if (!urls.length) return null;
  return chrome.runtime.sendMessage({
    action: "INGEST_DETAILS",
    source,
    urls,
  });
}

saveBtn.addEventListener("click", async () => {
  const detected = await detectPortal();
  if (!detected) return;
  const { portal, tabId } = detected;

  // HITL: request the portal's host permission only on this user gesture.
  // If the user already granted it (e.g. from a prior save) the call
  // returns true without re-prompting.
  const granted = await chrome.permissions.request({ origins: [portal.origin] });
  if (!granted) {
    setStatus("Permission denied", "err");
    return;
  }

  saveBtn.disabled = true;
  const originalLabel = saveBtn.textContent;
  saveBtn.textContent = "Parsing…";
  try {
    const parsed = await chrome.tabs.sendMessage(tabId, { action: "PARSE_LISTING" });
    if (!parsed?.ok) {
      throw new Error(parsed?.error || "Content script returned no result");
    }
    if (!parsed.postings?.length) {
      throw new Error("No jobs visible — scroll the listing first, then click Save.");
    }

    saveBtn.textContent = "Sending…";
    const ingest = await chrome.runtime.sendMessage({
      action: "INGEST_LISTING",
      source: portal.source,
      postings: parsed.postings,
    });
    if (!ingest?.ok) {
      throw new Error(ingest?.error || "Ingest failed");
    }

    setStatus(
      `Saved ${ingest.accepted} (${ingest.skipped_existing} dup), fetching details…`,
      "ok",
    );
    await refreshLastSave();

    // Auto-trigger detail fetch for the freshly accepted URLs (PR6).
    const acceptedIndices = Array.isArray(ingest.accepted_indices)
      ? ingest.accepted_indices
      : [];
    const detailUrls = acceptedIndices
      .map((i) => parsed.postings[i]?.url)
      .filter(Boolean);

    if (detailUrls.length === 0) {
      setStatus(
        `Saved ${ingest.accepted} (${ingest.skipped_existing} dup) — nothing new to detail-fetch`,
        "ok",
      );
    } else {
      saveBtn.textContent = "Fetching details…";
      const details = await triggerDetailsForUrls(portal.source, detailUrls);
      if (details?.ok) {
        const failedNote = details.failed > 0 ? `, ${details.failed} failed` : "";
        setStatus(
          `Saved ${ingest.accepted}, filled ${details.updated}${failedNote}`,
          details.failed > 0 ? "warn" : "ok",
        );
      } else {
        setStatus(
          `Saved ${ingest.accepted}, detail fetch failed: ${details?.error || "unknown"}`,
          "err",
        );
      }
    }
  } catch (err) {
    console.error("[popup] save failed", err);
    setStatus(`Failed: ${err?.message || err}`, "err");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = originalLabel;
    await refreshSaveButton();
    await refreshErrors();
    await refreshRetryButton();
  }
});

retryBtn.addEventListener("click", async () => {
  const urls = await collectFailedDetailUrls();
  if (!urls.length) return;

  // Derive source by URL host. PR7 / PR8 grow this map.
  const matchedPortal = PORTALS.find((p) => urls.every((u) => p.matchesUrl(u)));
  if (!matchedPortal) {
    setStatus("Mixed-source retry not supported yet", "err");
    return;
  }

  const granted = await chrome.permissions.request({ origins: [matchedPortal.origin] });
  if (!granted) {
    setStatus("Permission denied", "err");
    return;
  }

  retryBtn.disabled = true;
  const originalLabel = retryBtn.textContent;
  retryBtn.textContent = "Retrying…";
  try {
    const details = await triggerDetailsForUrls(matchedPortal.source, urls);
    if (details?.ok) {
      const failedNote = details.failed > 0 ? `, ${details.failed} still failed` : "";
      setStatus(`Retry: filled ${details.updated}${failedNote}`, details.failed > 0 ? "warn" : "ok");
      // Drop entries we just retried successfully (best-effort: SW didn't tell us
      // which URLs succeeded individually, so we drop ALL retried entries — the
      // failed ones will reappear in the SW's persistErrors() call).
      const { errors: cur = [] } = await chrome.storage.local.get("errors");
      const retried = new Set(urls);
      const remaining = cur.filter(
        (e) => !(e.action === "INGEST_DETAILS" && retried.has(e.url)),
      );
      await chrome.storage.local.set({ errors: remaining });
    } else {
      setStatus(`Retry failed: ${details?.error || "unknown"}`, "err");
    }
  } finally {
    retryBtn.textContent = originalLabel;
    await refreshErrors();
    await refreshRetryButton();
  }
});

openOptionsLink.addEventListener("click", (event) => {
  event.preventDefault();
  chrome.runtime.openOptionsPage();
});

document.addEventListener("DOMContentLoaded", () => {
  pollHealth();
  refreshLastSave();
  refreshErrors();
  refreshSaveButton();
  refreshRetryButton();
});
