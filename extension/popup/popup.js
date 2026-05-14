// Popup script — runs each time the popup opens.
//
// Responsibilities:
//   - Poll /api/health via the SW and paint the status pill
//   - Surface last save + recent errors from chrome.storage.local
//   - Detect the active tab's portal, enable the Save button accordingly
//   - On Save click: request portal host permission (HITL user gesture),
//     ask the content script to PARSE_LISTING, forward the result to the
//     SW for INGEST_LISTING, surface the response

const statusEl = document.getElementById("status");
const lastSaveEl = document.getElementById("last-save");
const errorsCountEl = document.getElementById("errors-count");
const errorsListEl = document.getElementById("errors-list");
const openOptionsLink = document.getElementById("open-options");
const saveBtn = document.getElementById("save-btn");

// Per-portal listing-page detector. PR7 will append NFJ; PR8 LinkedIn.
const PORTALS = [
  {
    source: "jjit",
    label: "Just Join IT",
    origin: "https://justjoin.it/*",
    isListingUrl(urlStr) {
      try {
        const u = new URL(urlStr);
        // Listing lives at the root (with optional query params for filters).
        // Detail pages /job-offer/... are intentionally excluded.
        return u.hostname === "justjoin.it" && (u.pathname === "/" || u.pathname === "");
      } catch {
        return false;
      }
    },
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
    li.textContent = `${ts} ${entry.action || ""}: ${entry.reason || ""}`.trim();
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

saveBtn.addEventListener("click", async () => {
  const detected = await detectPortal();
  if (!detected) return;
  const { portal, tabId } = detected;

  // HITL: request the portal's host permission only on this user gesture.
  // If the user has already granted it (e.g. from a prior save), the call
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
      `Saved ${ingest.accepted} (${ingest.skipped_existing} dup)`,
      "ok",
    );
    await refreshLastSave();
    await refreshErrors();
  } catch (err) {
    console.error("[popup] save failed", err);
    setStatus(`Failed: ${err?.message || err}`, "err");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = originalLabel;
    refreshSaveButton();
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
});
