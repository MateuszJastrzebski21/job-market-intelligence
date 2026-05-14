// Parses the HTML response of a JJIT job-offer detail page into clean
// description text + raw HTML for downstream LLM extraction.
//
// MCP-driven DOM inspection 2026-05-14 — see docs/jjit-selectors.md
// "Detail page selectors". Strategy:
//   - Find <h3> matching {"Job description", "Opis stanowiska"} (JJIT
//     serves either depending on locale)
//   - Take .nextElementSibling — the description container
//   - description_html = sibling.innerHTML
//   - description_text = block-aware walk of sibling (plain .textContent
//     flattens paragraphs together — unusable for the LLM extractor)
//
// Module shape: classic JS, declares parseJJITDetail on the global so
// offscreen.html can load it via <script src=> alongside offscreen.js.
// MV3 offscreen documents support ES modules, but staying classic keeps
// us symmetric with lib/parsers/jjit-listing.js (PR5) and dodges the
// content-script ESM gap. Bottom module.exports lets vitest import via
// createRequire.

(function () {
  const SECTION_HEADINGS = ["Job description", "Opis stanowiska"];
  const BLOCK_TAGS = new Set([
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "blockquote", "pre", "section", "article",
  ]);

  function parseJJITDetail(html, _url) {
    if (!html || typeof html !== "string") {
      return emptyResult();
    }
    const doc = new DOMParser().parseFromString(html, "text/html");
    const heading = findDescriptionHeading(doc);
    if (!heading) {
      console.warn("[JJIT detail parser] no description heading found");
      return emptyResult();
    }
    const sibling = heading.nextElementSibling;
    if (!sibling) {
      console.warn("[JJIT detail parser] description heading has no sibling");
      return emptyResult();
    }
    return {
      description_html: sibling.innerHTML.trim(),
      description_text: extractText(sibling),
      raw_payload_patch: {},
    };
  }

  function emptyResult() {
    return { description_html: "", description_text: "", raw_payload_patch: {} };
  }

  function findDescriptionHeading(doc) {
    for (const h3 of doc.querySelectorAll("h3")) {
      const text = (h3.textContent || "").trim();
      if (SECTION_HEADINGS.includes(text)) return h3;
    }
    return null;
  }

  function extractText(root) {
    const out = [];
    walk(root, out);
    return out
      .join("")
      .replace(/[ \t]+\n/g, "\n")  // strip trailing spaces before newlines
      .replace(/\n{3,}/g, "\n\n")  // collapse 3+ newlines into 2
      .trim();
  }

  function walk(el, out) {
    for (const node of el.childNodes) {
      if (node.nodeType === 3 /* TEXT_NODE */) {
        const text = node.textContent;
        if (text) out.push(text);
        continue;
      }
      if (node.nodeType !== 1 /* ELEMENT_NODE */) continue;
      const tag = node.tagName.toLowerCase();
      if (tag === "br") {
        out.push("\n");
        continue;
      }
      if (tag === "li") {
        out.push("\n- ");
        walk(node, out);
        continue;
      }
      const isBlock = BLOCK_TAGS.has(tag);
      if (isBlock) out.push("\n");
      walk(node, out);
      if (isBlock) out.push("\n");
    }
  }

  // Browser global (offscreen.js calls this via the global scope)
  globalThis.parseJJITDetail = parseJJITDetail;

  // Vitest CJS interop
  if (typeof module !== "undefined" && typeof module.exports !== "undefined") {
    module.exports = { parseJJITDetail };
  }
})();
