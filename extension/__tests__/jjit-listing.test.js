import { describe, it, expect, vi, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { parseJJITListing } = require("../lib/parsers/jjit-listing.js");

function load(name) {
  const html = readFileSync(join(__dirname, "fixtures", name), "utf8");
  return new DOMParser().parseFromString(html, "text/html");
}

describe("parseJJITListing", () => {
  it("parses 2 cards from the 2-card fixture", () => {
    const result = parseJJITListing(load("jjit-listing-2-cards.html"));
    expect(result.cardCount).toBe(2);
    expect(result.postings).toHaveLength(2);
    expect(result.errors).toEqual([]);
  });

  it("extracts source_id from the URL slug", () => {
    const result = parseJJITListing(load("jjit-listing-2-cards.html"));
    expect(result.postings[0].source_id).toBe(
      "acmecorp-python-backend-developer-warsaw-python",
    );
    expect(result.postings[1].source_id).toBe(
      "synthetic-inc-junior-data-engineer-remote-data",
    );
  });

  it("captures title, company, location, salary, tech_stack on a full card", () => {
    const result = parseJJITListing(load("jjit-listing-2-cards.html"));
    const first = result.postings[0];
    expect(first.title).toBe("Python Backend Developer");
    expect(first.company_name).toBe("Acme Corp");
    expect(first.location_raw).toBe("Warsaw");
    expect(first.salary_raw).toBe("15 000 - 25 000 PLN/month");
    expect(first.raw_payload.tech_stack).toEqual([
      "Python",
      "FastAPI",
      "PostgreSQL",
    ]);
    expect(first.raw_payload.seniority_label).toBe("Senior");
    expect(first.raw_payload.working_time_label).toBe("Permanent");
  });

  it("returns null salary_raw when no spans match digit+dash pattern", () => {
    const result = parseJJITListing(load("jjit-listing-2-cards.html"));
    const second = result.postings[1];
    expect(second.salary_raw).toBeNull();
    expect(second.raw_payload.seniority_label).toBe("Junior");
    expect(second.raw_payload.working_time_label).toBe("B2B");
  });

  it("absolutizes the URL to https://justjoin.it", () => {
    const result = parseJJITListing(load("jjit-listing-2-cards.html"));
    expect(result.postings[0].url).toBe(
      "https://justjoin.it/job-offer/acmecorp-python-backend-developer-warsaw-python",
    );
  });

  it("handles multi-location strings without crashing", () => {
    const result = parseJJITListing(load("jjit-listing-2-cards.html"));
    expect(result.postings[1].location_raw).toBe("Krakow, +2 Locations");
  });

  describe("defensive paths", () => {
    beforeEach(() => {
      vi.spyOn(console, "warn").mockImplementation(() => {});
    });

    it("skips cards missing <h3> without throwing (logs to console)", () => {
      const result = parseJJITListing(load("jjit-listing-no-title.html"));
      expect(result.cardCount).toBe(2);
      expect(result.postings).toHaveLength(1);
      expect(result.postings[0].title).toBe("Valid Card");
      expect(console.warn).toHaveBeenCalled();
    });

    it("returns empty result with diagnostic error when container missing", () => {
      const result = parseJJITListing(load("jjit-listing-empty.html"));
      expect(result.cardCount).toBe(0);
      expect(result.postings).toEqual([]);
      expect(result.errors[0]).toMatch(/up-offers-list/);
    });
  });
});
