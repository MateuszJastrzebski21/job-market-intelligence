// HTTP client for the JMI ingest endpoint.
//
// All requests use JSON bodies. Authenticated endpoints carry the
// X-Ingest-Token header sourced from chrome.storage.sync (set via the
// options page). /api/health is no-auth; the popup uses it on open.

const DEFAULT_TIMEOUT_MS = 10_000;

export async function readSettings() {
  const stored = await chrome.storage.sync.get(["jmiUrl", "ingestToken"]);
  return {
    baseUrl: (stored.jmiUrl || "http://127.0.0.1:8000").replace(/\/+$/, ""),
    token: stored.ingestToken || "",
  };
}

export class JmiClient {
  constructor(baseUrl, token, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
    this.baseUrl = (baseUrl || "").replace(/\/+$/, "");
    this.token = token || "";
    this.timeoutMs = timeoutMs;
  }

  _headers({ authed }) {
    const headers = { "Content-Type": "application/json" };
    if (authed) headers["X-Ingest-Token"] = this.token;
    return headers;
  }

  async _fetch(path, init) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = body && body.detail ? body.detail : response.statusText;
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }
      return body;
    } finally {
      clearTimeout(timer);
    }
  }

  async health() {
    return this._fetch("/api/health", {
      method: "GET",
      headers: this._headers({ authed: false }),
    });
  }

  async ingest(source, postings) {
    return this._fetch("/api/ingest", {
      method: "POST",
      headers: this._headers({ authed: true }),
      body: JSON.stringify({ source, postings }),
    });
  }

  async details(source, details) {
    return this._fetch("/api/details", {
      method: "POST",
      headers: this._headers({ authed: true }),
      body: JSON.stringify({ source, details }),
    });
  }
}
