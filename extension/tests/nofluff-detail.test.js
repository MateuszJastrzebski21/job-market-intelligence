import { describe, it, expect, vi, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { parseNFJDetail } = require("../lib/parsers/nofluff-detail.js");

function load(name) {
  return readFileSync(join(__dirname, "fixtures", name), "utf8");
}

describe("parseNFJDetail", () => {
  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("extracts description_html from common-posting-content-wrapper", () => {
    const result = parseNFJDetail(load("nofluff-detail-sample.html"));
    expect(result.description_html.length).toBeGreaterThan(50);
    expect(result.description_html).toContain("posting-description");
    expect(result.raw_payload_patch).toEqual({});
  });

  it("concatenates text from all five section types", () => {
    const result = parseNFJDetail(load("nofluff-detail-sample.html"));
    expect(result.description_text).toContain("Dołączysz do projektu"); // #posting-description
    expect(result.description_text).toContain("Projektowanie architektury"); // #posting-tasks
    expect(result.description_text).toContain("Python, SQL"); // must-have ("Obowiązkowe")
    expect(result.description_text).toContain("Minimum trzy lata"); // requirements ("Opis wymagań")
    expect(result.description_text).toContain("Power BI oraz IoT"); // #posting-nice-to-have
  });

  it("does not pull in #posting-specs (not part of the description)", () => {
    const result = parseNFJDetail(load("nofluff-detail-sample.html"));
    expect(result.description_text).not.toContain("Tryb rekrutacji");
  });

  it("preserves Polish characters (UTF-8 round-trip)", () => {
    const result = parseNFJDetail(load("nofluff-detail-sample.html"));
    expect(result.description_text).toMatch(/[ąćęłóż]/);
    expect(result.description_text).toContain("Warszawa");
  });

  it("does not crash when optional sections are absent", () => {
    const result = parseNFJDetail(load("nofluff-detail-minimal.html"));
    expect(result.description_text).toContain("Krótki opis stanowiska");
    expect(result.description_html.length).toBeGreaterThan(0);
  });

  it("returns empty result when no #posting-description section is present", () => {
    const result = parseNFJDetail(
      "<html><body><h1>Page not found</h1></body></html>",
    );
    expect(result.description_html).toBe("");
    expect(result.description_text).toBe("");
    expect(result.raw_payload_patch).toEqual({});
    expect(console.warn).toHaveBeenCalled();
  });

  it("handles empty / non-string html gracefully", () => {
    const empty = { description_html: "", description_text: "", raw_payload_patch: {} };
    expect(parseNFJDetail("")).toEqual(empty);
    expect(parseNFJDetail(null)).toEqual(empty);
  });
});
