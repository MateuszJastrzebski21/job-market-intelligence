// User-facing notifications via chrome.notifications.create.

const ICON_URL = chrome.runtime.getURL("icons/48.png");

const TITLES = {
  ok: "JMI",
  warn: "JMI — warning",
  err: "JMI — error",
};

let counter = 0;

export function showToast({ type = "ok", text, ttlMs = 4000 } = {}) {
  if (!text) return;
  const id = `jmi-toast-${++counter}`;
  chrome.notifications.create(id, {
    type: "basic",
    iconUrl: ICON_URL,
    title: TITLES[type] || TITLES.ok,
    message: text,
  });
  if (ttlMs > 0) {
    setTimeout(() => chrome.notifications.clear(id), ttlMs);
  }
}
