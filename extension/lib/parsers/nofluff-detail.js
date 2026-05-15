// Parses the HTML response of a NoFluffJobs /{locale}/job/{slug} detail page
// into clean description text + raw HTML for downstream LLM extraction.
//
// MCP-driven DOM inspection 2026-05-15 — see docs/nofluff-selectors.md
// "Detail page selectors". Strategy:
//   - description_html = innerHTML of <common-posting-content-wrapper>
//   - description_text = concatenated textContent of five <section> blocks:
//       #posting-description, #posting-tasks, the id-less must-have section
//       (<h2> "Obowiązkowe"), the id-less requirements section (<h2> "Opis
//       wymagań"), and #posting-nice-to-have.
//   - Section ids are locale-independent, so the id'd sections need no PL/EN
//     heading match; the two id-less sections are reached via PL <h2> text.
//
// Module shape: classic JS wrapped in an IIFE, declares parseNFJDetail on the
// global so offscreen.html can load it via <script src=> alongside
// offscreen.js. Bottom module.exports lets vitest import via createRequire.

(function () {
  const MUST_HAVE_HEADING = "Obowiązkowe";
  const REQUIREMENTS_HEADING = "Opis wymagań";

  function parseNFJDetail(html, _url) {
    if (!html || typeof html !== "string") {
      return emptyResult();
    }
    const doc = new DOMParser().parseFromString(html, "text/html");

    const descSection = doc.querySelector("section#posting-description");
    if (!descSection) {
      console.warn("[NFJ detail parser] no section#posting-description found");
      return emptyResult();
    }

    const wrapper = doc.querySelector("common-posting-content-wrapper");
    const descriptionHtml = wrapper ? wrapper.innerHTML.trim() : "";

    const sections = [
      descSection,
      doc.querySelector("section#posting-tasks"),
      sectionByHeading(doc, MUST_HAVE_HEADING),
      sectionByHeading(doc, REQUIREMENTS_HEADING),
      doc.querySelector("section#posting-nice-to-have"),
    ];
    const descriptionText = sections
      .map((s) => (s ? normalizeText(s.textContent || "") : ""))
      .filter(Boolean)
      .join("\n\n");

    return {
      description_html: descriptionHtml,
      description_text: descriptionText,
      raw_payload_patch: {}, // Rich extraction deferred — PR15 captures prose only.
    };
  }

  function emptyResult() {
    return { description_html: "", description_text: "", raw_payload_patch: {} };
  }

  // The must-have / requirements sections carry no id — locate them by their
  // <h2> heading text. The section either wraps the heading or follows it.
  function sectionByHeading(doc, headingText) {
    for (const h2 of doc.querySelectorAll("h2")) {
      if (normalizeText(h2.textContent || "") !== headingText) continue;
      const ancestor = h2.closest("section");
      if (ancestor && !ancestor.id) return ancestor;
      const sib = h2.nextElementSibling;
      if (sib && sib.tagName && sib.tagName.toLowerCase() === "section") return sib;
      return ancestor || null;
    }
    return null;
  }

  function normalizeText(text) {
    return text.replace(/\s+/g, " ").trim();
  }

  // Browser global (offscreen.js calls this via the global scope)
  globalThis.parseNFJDetail = parseNFJDetail;

  // Vitest CJS interop
  if (typeof module !== "undefined" && typeof module.exports !== "undefined") {
    module.exports = { parseNFJDetail };
  }
})();
