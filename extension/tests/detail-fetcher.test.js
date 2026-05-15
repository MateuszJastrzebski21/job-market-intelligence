import { describe, it, expect } from "vitest";

const { extractSlug } = await import("../background/detail-fetcher.js");

describe("extractSlug (source-aware)", () => {
  it("extracts the JJIT slug from a /job-offer/ URL", () => {
    expect(
      extractSlug("https://justjoin.it/job-offer/acme-python-dev-warsaw", "jjit"),
    ).toBe("acme-python-dev-warsaw");
  });

  it("defaults to the JJIT pattern when no source is given", () => {
    expect(extractSlug("https://justjoin.it/job-offer/some-slug")).toBe("some-slug");
  });

  it("extracts the NFJ slug from a /pl/job/ URL", () => {
    expect(
      extractSlug(
        "https://nofluffjobs.com/pl/job/data-scientist-acme-corp-warszawa",
        "nofluff",
      ),
    ).toBe("data-scientist-acme-corp-warszawa");
  });

  it("extracts the NFJ slug from an /en/job/ URL", () => {
    expect(
      extractSlug("https://nofluffjobs.com/en/job/backend-developer-acme", "nofluff"),
    ).toBe("backend-developer-acme");
  });

  it("strips query string and hash from the NFJ slug", () => {
    expect(
      extractSlug("https://nofluffjobs.com/pl/job/devops-acme?ref=feed#top", "nofluff"),
    ).toBe("devops-acme");
  });

  it("returns null when a JJIT URL is parsed with the nofluff source", () => {
    expect(
      extractSlug("https://justjoin.it/job-offer/some-slug", "nofluff"),
    ).toBeNull();
  });

  it("returns null for garbage / empty input", () => {
    expect(extractSlug("not a url", "nofluff")).toBeNull();
    expect(extractSlug("", "jjit")).toBeNull();
    expect(extractSlug(null, "nofluff")).toBeNull();
  });
});
