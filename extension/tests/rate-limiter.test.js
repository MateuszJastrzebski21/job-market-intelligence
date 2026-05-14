import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
// rate-limiter.js is an ES module, but vitest can interop both ways. Using
// dynamic import avoids the createRequire CJS path for ESM-native files.
const { RateLimitedQueue } = await import("../lib/rate-limiter.js");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

describe("RateLimitedQueue", () => {
  it("respects minGapMs between starts", async () => {
    const q = new RateLimitedQueue({ minGapMs: 60, maxConcurrent: 10 });
    const startTimes = [];
    const tasks = [1, 2, 3, 4, 5].map((i) =>
      q.add(async () => {
        startTimes.push(Date.now());
        await sleep(10);
        return i;
      }),
    );
    const results = await Promise.all(tasks);
    expect(results).toEqual([1, 2, 3, 4, 5]);
    for (let i = 1; i < startTimes.length; i++) {
      const gap = startTimes[i] - startTimes[i - 1];
      // Allow ~10ms scheduler jitter under the 60ms gap target.
      expect(gap).toBeGreaterThanOrEqual(50);
    }
  });

  it("respects maxConcurrent", async () => {
    const q = new RateLimitedQueue({ minGapMs: 0, maxConcurrent: 3 });
    let inFlight = 0;
    let peak = 0;
    const tasks = Array.from({ length: 12 }, () =>
      q.add(async () => {
        inFlight++;
        peak = Math.max(peak, inFlight);
        await sleep(20);
        inFlight--;
      }),
    );
    await Promise.all(tasks);
    expect(peak).toBeLessThanOrEqual(3);
  });

  it("rejection in one task does not poison subsequent tasks", async () => {
    const q = new RateLimitedQueue({ minGapMs: 0, maxConcurrent: 1 });
    await expect(
      q.add(async () => {
        throw new Error("nope");
      }),
    ).rejects.toThrow("nope");

    const okResult = await q.add(async () => "ok");
    expect(okResult).toBe("ok");
  });

  it("all queued tasks complete (no deadlock)", async () => {
    const q = new RateLimitedQueue({ minGapMs: 5, maxConcurrent: 2 });
    const results = await Promise.all(
      Array.from({ length: 10 }, (_, i) => q.add(async () => i)),
    );
    expect(results).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  it("returns task value via the promise resolution", async () => {
    const q = new RateLimitedQueue({ minGapMs: 0, maxConcurrent: 1 });
    const result = await q.add(async () => ({ a: 1, b: 2 }));
    expect(result).toEqual({ a: 1, b: 2 });
  });
});
