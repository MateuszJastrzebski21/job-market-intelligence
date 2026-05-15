import { describe, it, expect } from "vitest";

const { isJJITListingUrl, isJJITUrl, isNFJListingUrl, isNFJUrl } = await import(
  "../lib/url-matchers.js"
);

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

describe("isNFJListingUrl", () => {
  describe("matches listing pages", () => {
    it.each([
      ["root (redirects to /pl)", "https://nofluffjobs.com/"],
      ["PL curated landing", "https://nofluffjobs.com/pl"],
      ["PL landing trailing slash", "https://nofluffjobs.com/pl/"],
      ["PL category job board", "https://nofluffjobs.com/pl/backend"],
      ["EN curated landing", "https://nofluffjobs.com/en"],
      ["EN category job board", "https://nofluffjobs.com/en/devops"],
      ["PL category + query filter", "https://nofluffjobs.com/pl/backend?criteria=seniority%3Djunior"],
      ["/pl/jobs (NFJ redirects to /pl, URL still matches)", "https://nofluffjobs.com/pl/jobs"],
    ])("%s → true", (_label, url) => {
      expect(isNFJListingUrl(url)).toBe(true);
    });
  });

  describe("excludes non-listing pages", () => {
    it.each([
      ["PL detail page", "https://nofluffjobs.com/pl/job/some-slug-here"],
      ["EN detail page", "https://nofluffjobs.com/en/job/some-slug"],
      ["PL company profile", "https://nofluffjobs.com/pl/company/foo"],
      ["EN company profile", "https://nofluffjobs.com/en/company/acme-12345"],
      ["different host (JJIT)", "https://justjoin.it/"],
      ["non-https scheme", "http://nofluffjobs.com/pl"],
    ])("%s → false", (_label, url) => {
      expect(isNFJListingUrl(url)).toBe(false);
    });

    it("invalid URL string → false (no throw)", () => {
      expect(isNFJListingUrl("not a url")).toBe(false);
      expect(isNFJListingUrl("")).toBe(false);
      expect(isNFJListingUrl(null)).toBe(false);
      expect(isNFJListingUrl(undefined)).toBe(false);
    });
  });
});

describe("isNFJUrl", () => {
  it.each([
    ["landing", "https://nofluffjobs.com/pl"],
    ["detail page", "https://nofluffjobs.com/pl/job/abc"],
    ["company profile", "https://nofluffjobs.com/pl/company/foo"],
  ])("%s → true (matches NFJ host)", (_label, url) => {
    expect(isNFJUrl(url)).toBe(true);
  });

  it.each([
    ["different host", "https://justjoin.it/"],
    ["non-https", "http://nofluffjobs.com/"],
    ["empty", ""],
    ["garbage", "not-a-url"],
  ])("%s → false", (_label, url) => {
    expect(isNFJUrl(url)).toBe(false);
  });
});
