# JMI Job Saver — Chrome Extension

**Status:** Phase 1 PR4 — skeleton. Portal logic lands in PR5+ (JJIT content script) and PR7 (NoFluffJobs). LinkedIn is deferred to PR8.

This is a Manifest V3 Chrome extension that lets you save job postings from supported portals into your local [JMI backend](../docs/extension-plan.md) via Human-in-the-Loop ingestion (per [ADR-0009](../docs/adr/0009-hitl-ingestion-pivot.md)). The extension is intended to be loaded as **unpacked / developer-mode**; it is not distributed via the Chrome Web Store.

## What ships in PR4

- Loadable unpacked extension (`chrome://extensions/` → Load unpacked → select `extension/`)
- Popup with **JMI status** indicator (polls `/api/health` via the service worker on open)
- Options page for the JMI URL + ingest token, with a Test connection button
- Background service worker skeleton — routes three messages: `HEALTH_CHECK` (wired), `INGEST_LISTING` (stub, PR5), `INGEST_DETAILS` (stub, PR6)
- Library code: `JmiClient` (fetch wrapper), `showToast` (notifications), `RateLimitedQueue` (class signature only; PR6 implements)
- Placeholder solid-color icons (16/48/128) generated via Python stdlib zlib+struct — designed for replacement in Phase 5+

## Load unpacked

1. Open `chrome://extensions/`
2. Toggle **Developer mode** (top-right)
3. Click **Load unpacked**
4. Select the `extension/` directory
5. Pin the extension to the toolbar (puzzle icon → pin)

## Configuration

1. Click the extension icon → **Settings**
2. **JMI URL**: default `http://127.0.0.1:8000` (host_permissions auto-granted on install for clean first-run UX)
3. **Ingest token**: paste the value of `JMI_INGEST_TOKEN` from your backend `.env`
4. Click **Save settings**
5. Click **Test connection** — should show `ok — db_ok=true, version=0.1.0`

## Permissions

| Type | Hosts | Why |
|---|---|---|
| `host_permissions` | `http://127.0.0.1:8000/*` | Auto-granted at install. localhost = your own machine; no third-party privacy concern. |
| `optional_host_permissions` | `justjoin.it`, `nofluffjobs.com`, `linkedin.com` | Granted per-portal on first save (in PR5+ when content scripts ship). |

Other permissions: `storage` (settings + lastSave/errors), `activeTab` (popup → tab queries), `notifications` (toast surfaces).

## Development

1. Edit files in `extension/`
2. Open `chrome://extensions/` → click the reload icon on the extension card
3. Re-open the popup (and re-open the SW DevTools if you're debugging there)

To inspect the service worker logs:
- `chrome://extensions/` → JMI Job Saver → **service worker** link → DevTools opens for the SW context

## Roadmap

| PR | Scope |
|---|---|
| **PR4 (this)** | Skeleton — no portal logic, no detail fetcher |
| PR5 | JJIT content script + listing parser (wires `INGEST_LISTING`) |
| PR6 | Background detail fetcher + rate limiter (wires `INGEST_DETAILS`, offscreen-document DOMParser) |
| PR7 | NoFluffJobs content script + listing parser |
| PR8 | LinkedIn content script (deferred to second wave) |

See [`docs/extension-plan.md`](../docs/extension-plan.md) for the full architecture.
