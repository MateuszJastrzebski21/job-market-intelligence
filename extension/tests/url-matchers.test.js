import { describe, it, expect } from "vitest";

const { isJJITListingUrl, isJJITUrl } = await import("../lib/url-matchers.js");

describe("isJJITListingUrl", () => {
  describe("matches listing pages", () => {
    it.each([
      ["root", "https://justjoin.it/"],
      ["root + query (single filter)", "https://justjoin.it/?with-salary=yes"],
      ["root + query (multiple filters)", "https://justjoin.it/?with-salary=yes&experience-level=junior"],
      ["category filter under all-locations", "https://justjoin.it/job-offers/all-locations/ai"],
      ["bare location filter", "https://justjoin.it/job-offers/warszawa"],
      ["location + category combo", "https://justjoin.it/job-offers/krakow/python"],
      ["job-offers/ trailing slash", "https://justjoin.it/job-offers/"],
    ])("%s → true", (_label, url) => {
      expect(isJJITListingUrl(url)).toBe(true);
    });
  });

  describe("excludes non-listing pages", () => {
    it.each([
      ["detail page (singular job-offer)", "https://justjoin.it/job-offer/some-slug-here"],
      ["static regulamin page", "https://justjoin.it/regulamin"],
      ["admin path", "https://justjoin.it/admin/"],
      ["bare /job-offers (no trailing slash)", "https://justjoin.it/job-offers"],
      ["different host (typo)", "https://justjoin.io/"],
      ["different host entirely", "https://nofluffjobs.com/"],
      ["non-https scheme", "http://justjoin.it/"],
    ])("%s → false", (_label, url) => {
      expect(isJJITListingUrl(url)).toBe(false);
    });

    it("invalid URL string → false (no throw)", () => {
      expect(isJJITListingUrl("not a url")).toBe(false);
      expect(isJJITListingUrl("")).toBe(false);
      expect(isJJITListingUrl(null)).toBe(false);
      expect(isJJITListingUrl(undefined)).toBe(false);
    });
  });
});

describe("isJJITUrl", () => {
  it.each([
    ["listing root", "https://justjoin.it/"],
    ["detail page", "https://justjoin.it/job-offer/abc"],
    ["regulamin", "https://justjoin.it/regulamin"],
    ["filtered listing", "https://justjoin.it/job-offers/warszawa"],
  ])("%s → true (matches JJIT host)", (_label, url) => {
    expect(isJJITUrl(url)).toBe(true);
  });

  it.each([
    ["different host", "https://nofluffjobs.com/"],
    ["typo host", "https://justjoin.io/"],
    ["empty", ""],
    ["garbage", "not-a-url"],
  ])("%s → false", (_label, url) => {
    expect(isJJITUrl(url)).toBe(false);
  });
});
