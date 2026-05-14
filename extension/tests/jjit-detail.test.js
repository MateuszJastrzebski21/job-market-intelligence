import { describe, it, expect, vi, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { parseJJITDetail } = require("../lib/parsers/jjit-detail.js");

function load(name) {
  return readFileSync(join(__dirname, "fixtures", name), "utf8");
}

describe("parseJJITDetail", () => {
  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("extracts description_html + description_text from a JJIT detail page", () => {
    const result = parseJJITDetail(
      load("jjit-detail-sample.html"),
      "https://justjoin.it/job-offer/test",
    );
    expect(result.description_html.length).toBeGreaterThan(50);
    expect(result.description_text.length).toBeGreaterThan(100);
    expect(result.raw_payload_patch).toEqual({});
  });

  it("matches the Polish heading 'Opis stanowiska'", () => {
    const result = parseJJITDetail(load("jjit-detail-pl.html"));
    expect(result.description_text).toMatch(/Cloud/);
    expect(result.description_text.length).toBeGreaterThan(50);
  });

  it("preserves Polish characters (UTF-8 round-trip)", () => {
    const result = parseJJITDetail(load("jjit-detail-sample.html"));
    expect(result.description_text).toMatch(/[ąćęłóż]/);
  });

  it("formats <li> children with '- ' bullet markers", () => {
    const result = parseJJITDetail(load("jjit-detail-sample.html"));
    expect(result.description_text).toMatch(/\n- /);
  });

  it("collapses runs of more than two blank lines", () => {
    const result = parseJJITDetail(load("jjit-detail-sample.html"));
    expect(result.description_text).not.toMatch(/\n\n\n/);
  });

  it("returns empty result when no description heading is present", () => {
    const result = parseJJITDetail(
      "<html><body><h1>Page not found</h1></body></html>",
    );
    expect(result.description_html).toBe("");
    expect(result.description_text).toBe("");
    expect(console.warn).toHaveBeenCalled();
  });

  it("handles empty / non-string html gracefully", () => {
    expect(parseJJITDetail("")).toEqual({
      description_html: "",
      description_text: "",
      raw_payload_patch: {},
    });
    expect(parseJJITDetail(null)).toEqual({
      description_html: "",
      description_text: "",
      raw_payload_patch: {},
    });
  });

  it("skips earlier h3 sections (e.g. 'Tech stack') and matches the right one", () => {
    const result = parseJJITDetail(load("jjit-detail-sample.html"));
    // Tech stack section comes BEFORE Job description in the fixture
    // (mirrors the real page layout). Parser must not capture it.
    expect(result.description_html).not.toContain("Polish, Google Cloud");
  });
});
