import { JmiClient } from "../lib/jmi-client.js";

const urlInput = document.getElementById("jmi-url");
const tokenInput = document.getElementById("ingest-token");
const saveBtn = document.getElementById("save-btn");
const testBtn = document.getElementById("test-btn");
const msgEl = document.getElementById("msg");

const DEFAULT_URL = "http://127.0.0.1:8000";

function showMsg(text, kind = "ok") {
  msgEl.textContent = text;
  msgEl.classList.remove("ok", "err");
  msgEl.classList.add(kind);
}

async function loadCurrent() {
  const { jmiUrl, ingestToken } = await chrome.storage.sync.get([
    "jmiUrl",
    "ingestToken",
  ]);
  urlInput.value = jmiUrl || DEFAULT_URL;
  tokenInput.value = ingestToken || "";
}

saveBtn.addEventListener("click", async () => {
  const jmiUrl = urlInput.value.trim() || DEFAULT_URL;
  const ingestToken = tokenInput.value.trim();
  if (!ingestToken) {
    showMsg("Ingest token cannot be empty.", "err");
    return;
  }
  await chrome.storage.sync.set({ jmiUrl, ingestToken });
  showMsg(`Saved at ${new Date().toLocaleTimeString()}.`, "ok");
});

testBtn.addEventListener("click", async () => {
  const baseUrl = urlInput.value.trim() || DEFAULT_URL;
  const token = tokenInput.value.trim();
  showMsg("Testing…");
  try {
    const client = new JmiClient(baseUrl, token);
    const health = await client.health();
    if (health?.status === "ok") {
      showMsg(
        `ok — db_ok=${health.db_ok}, version=${health.version}`,
        health.db_ok ? "ok" : "err",
      );
    } else {
      showMsg(`Unexpected response: ${JSON.stringify(health)}`, "err");
    }
  } catch (err) {
    showMsg(`Failed: ${err?.message || err}`, "err");
  }
});

loadCurrent();
