import { describe, it, expect, vi, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { parseNFJListing } = require("../lib/parsers/nofluff-listing.js");

function load(name) {
  const html = readFileSync(join(__dirname, "fixtures", name), "utf8");
  return new DOMParser().parseFromString(html, "text/html");
}

describe("parseNFJListing", () => {
  it("parses 3 cards spread across multiple nfj-postings-list sections", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    expect(result.cardCount).toBe(3);
    expect(result.postings).toHaveLength(3);
    expect(result.errors).toEqual([]);
  });

  it("uses the URL slug as source_id and keeps the posting id in raw_payload", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    expect(result.postings[0].source_id).toBe(
      "python-backend-developer-acme-corp-warszawa",
    );
    expect(result.postings[0].raw_payload.nfj_posting_id).toBe("XOEYPPK5");
    expect(result.postings[1].raw_payload.nfj_posting_id).toBe("ABCD1234");
  });

  it("captures title, company, location, salary, tech_stack on a full card", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    const first = result.postings[0];
    expect(first.title).toBe("Python Backend Developer");
    expect(first.company_name).toBe("Acme Corp");
    expect(first.location_raw).toBe("Warszawa");
    expect(first.salary_raw).toBe("15 000 – 20 000 PLN");
    expect(first.raw_payload.tech_stack).toEqual([
      "Python",
      "FastAPI",
      "PostgreSQL",
    ]);
  });

  it("absolutizes the URL to https://nofluffjobs.com", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    expect(result.postings[0].url).toBe(
      "https://nofluffjobs.com/pl/job/python-backend-developer-acme-corp-warszawa",
    );
  });

  it("does not crash when optional fields are absent (no salary, no tech tags)", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    const second = result.postings[1];
    expect(second.salary_raw).toBeNull();
    expect(second.raw_payload.tech_stack).toEqual([]);
    expect(second.company_name).toBe("Acme Corp");
  });

  it("captures the primary location only on a multi-location card", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    // Card 3 renders "Zdalnie +1" with a popover listing the other cities.
    expect(result.postings[2].location_raw).toBe("Zdalnie");
  });

  it("preserves Polish characters (UTF-8 round-trip)", () => {
    const result = parseNFJListing(load("nofluff-listing-3-cards.html"));
    expect(result.postings[1].title).toMatch(/[ąćęłóź]/);
    expect(result.postings[1].location_raw).toBe("Kraków");
  });

  describe("defensive paths", () => {
    beforeEach(() => {
      vi.spyOn(console, "warn").mockImplementation(() => {});
    });

    it("skips cards missing a title without throwing (logs to console)", () => {
      const result = parseNFJListing(load("nofluff-listing-no-title.html"));
      expect(result.cardCount).toBe(2);
      expect(result.postings).toHaveLength(1);
      expect(result.postings[0].title).toBe("Valid Card");
      expect(console.warn).toHaveBeenCalled();
    });

    it("returns empty result with diagnostic error when no list section exists", () => {
      const result = parseNFJListing(load("nofluff-listing-empty.html"));
      expect(result.cardCount).toBe(0);
      expect(result.postings).toEqual([]);
      expect(result.errors[0]).toMatch(/nfj-postings-list/);
    });
  });
});
