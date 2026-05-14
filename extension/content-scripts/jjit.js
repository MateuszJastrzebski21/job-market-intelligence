// Content script for https://justjoin.it/* (registered in manifest content_scripts).
//
// Loaded alongside lib/parsers/jjit-listing.js as classic scripts in the same
// isolated world — `parseJJITListing` is a global declared by that file.
//
// HITL invariant: this script does NOT auto-parse on load. It registers a
// message listener and waits for the popup to dispatch PARSE_LISTING after
// the user clicks "Save jobs on this page".

console.log("[JMI JJIT] content script loaded");

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.action !== "PARSE_LISTING") return undefined;
  try {
    if (typeof parseJJITListing !== "function") {
      sendResponse({
        ok: false,
        error: "parseJJITListing not loaded — manifest js[] order broken?",
      });
      return undefined;
    }
    const result = parseJJITListing(document);
    sendResponse({ ok: true, ...result });
  } catch (err) {
    console.error("[JMI JJIT] parser error", err);
    sendResponse({
      ok: false,
      error: err && err.message ? err.message : String(err),
    });
  }
  // PARSE_LISTING is sync (parser doesn't await anything); no `return true`.
  return undefined;
});
