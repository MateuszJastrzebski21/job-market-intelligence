// Skeleton — PR6 fills in the real semantics. The background detail fetcher
// is the only intended consumer; the class signature ships here so the SW
// import wiring can be laid out in PR4 without changing exports later.
//
// Target semantics (PR6):
//   - minGapMs (default 500) — minimum spacing between *starts* of new tasks
//   - maxConcurrent (default 25) — upper bound on in-flight count
//   - Steady-state concurrency ≈ min(taskTimeMs / minGapMs, maxConcurrent)

export class RateLimitedQueue {
  constructor({ minGapMs = 500, maxConcurrent = 25 } = {}) {
    this._minGapMs = minGapMs;
    this._maxConcurrent = maxConcurrent;
    // TODO(PR6): _lastStartMs, _inFlight, _pending[], drain helpers.
  }

  // eslint-disable-next-line no-unused-vars
  async add(asyncFn) {
    // TODO(PR6): respect minGapMs between starts + maxConcurrent in-flight.
    throw new Error("RateLimitedQueue.add not implemented yet (lands in PR6).");
  }
}
