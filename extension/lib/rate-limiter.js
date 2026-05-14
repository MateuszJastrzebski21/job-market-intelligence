// Rate-limited task queue (PR6 implementation; PR4 shipped a stub class).
//
// Semantics (per ADR-0009 §5):
//   - minGapMs (default 500) — minimum elapsed time between *starts* of new
//     tasks. Two starts in the same tick is forbidden even if concurrency
//     allows it.
//   - maxConcurrent (default 25) — upper bound on simultaneously in-flight
//     tasks. A new task waits if the cap is reached.
//   - Steady-state concurrency ≈ min(taskTimeMs / minGapMs, maxConcurrent).
//     For 1s tasks at 500ms spacing the queue plateaus at ~2 in flight.
//
// Failure handling: a task whose `asyncFn` throws still releases its slot
// (try/finally), so a single bad task can't deadlock the queue.

export class RateLimitedQueue {
  constructor({ minGapMs = 500, maxConcurrent = 25 } = {}) {
    this._minGapMs = minGapMs;
    this._maxConcurrent = maxConcurrent;
    this._lastStartMs = 0;
    this._inFlight = 0;
    this._pending = []; // FIFO of { asyncFn, resolve, reject }
    this._scheduledRetryAt = 0;
  }

  async add(asyncFn) {
    return new Promise((resolve, reject) => {
      this._pending.push({ asyncFn, resolve, reject });
      this._tryRun();
    });
  }

  _tryRun() {
    if (this._inFlight >= this._maxConcurrent) return;
    if (this._pending.length === 0) return;
    const now = Date.now();
    const wait = Math.max(0, this._lastStartMs + this._minGapMs - now);
    if (wait > 0) {
      // Avoid stacking duplicate timers — schedule one retry at the soonest
      // opportunity. Subsequent _tryRun calls will overwrite if needed.
      const fireAt = now + wait;
      if (this._scheduledRetryAt !== fireAt) {
        this._scheduledRetryAt = fireAt;
        setTimeout(() => {
          this._scheduledRetryAt = 0;
          this._tryRun();
        }, wait);
      }
      return;
    }
    const task = this._pending.shift();
    this._lastStartMs = Date.now();
    this._inFlight += 1;
    Promise.resolve()
      .then(() => task.asyncFn())
      .then(
        (val) => task.resolve(val),
        (err) => task.reject(err),
      )
      .finally(() => {
        this._inFlight -= 1;
        this._tryRun();
      });
  }
}
