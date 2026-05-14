// Offscreen document message router — dispatches PARSE_DETAIL to the right
// per-portal parser. Parsers register themselves on globalThis (loaded as
// classic scripts in offscreen.html). Messages are routed by `target` so
// the SW's own onMessage listener doesn't conflict.

const PARSERS = {
  jjit: typeof globalThis.parseJJITDetail === "function" ? globalThis.parseJJITDetail : null,
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target !== "offscreen" || message?.action !== "PARSE_DETAIL") {
    return undefined;
  }
  try {
    const parser = PARSERS[message.source];
    if (!parser) {
      sendResponse({ ok: false, error: `No parser registered for source: ${message.source}` });
      return undefined;
    }
    const result = parser(message.html, message.url);
    sendResponse({ ok: true, ...result });
  } catch (err) {
    console.error("[offscreen] parser threw", err);
    sendResponse({ ok: false, error: err?.message || String(err) });
  }
  return undefined;
});
