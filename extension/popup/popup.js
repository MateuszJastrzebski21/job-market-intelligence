// Popup script — runs each time the popup opens.
//   - Queries the SW for /api/health and paints the status pill
//   - Surfaces last save + recent errors from chrome.storage.local
//   - "Save" and "Retry failed details" buttons are stubs in PR4;
//     PR5+ wires them via INGEST_LISTING / INGEST_DETAILS messages.

const statusEl = document.getElementById("status");
const lastSaveEl = document.getElementById("last-save");
const errorsCountEl = document.getElementById("errors-count");
const errorsListEl = document.getElementById("errors-list");
const openOptionsLink = document.getElementById("open-options");

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

openOptionsLink.addEventListener("click", (event) => {
  event.preventDefault();
  chrome.runtime.openOptionsPage();
});

document.addEventListener("DOMContentLoaded", () => {
  pollHealth();
  refreshLastSave();
  refreshErrors();
});
