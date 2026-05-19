# Audit Closure Verification — 2026-05-18 Audit

**Verified against:** `main` HEAD `8ed9c37` (after PRs #52–#57 merged).
**Audit source:** `docs/audit-2026-05-18.md` (audited HEAD `3fe5595`).
**Method:** four read-only sub-agents, each verifying a cohort of audit findings
against the current code (audit line numbers had shifted; located by content).
**Status:** committed — audit-closure record.

## Summary

The audit's Critical + High findings split into two kinds:

- **"Fix now" issues** — C1, C2, H2, H3, H4, H6 → **all 6 closed.**
- **"Design/build into Phase 3" issues** — H1, H5, H7 → deferred by design
  (the audit itself scoped these to PR-3.x). Phase 3 has not started, so their
  non-closure is the expected state. H7 is further along — its conventions are
  now written as binding constraints in `docs/phase3-design-constraints.md`.

| Tier | Issues | Closed | Deferred to Phase 3 |
|---|---|---|---|
| Critical | C1, C2 | **2 / 2** | — |
| High | H1–H7 | **4 / 7** (H2, H3, H4, H6) | 3 (H1, H5, H7) |

**Phase 3 readiness:** the audit's verdict required the two Critical items
resolved before Phase 3 — both are. Phase 3 is unblocked; H1 must be designed
into PR-3.1 when that work starts.

**Dev tooling baseline checklist: 7 / 7** verified on current `main`.

## Critical

### C1 — LLM refusal guard — VERIFIED (closed)
`src/jmi/extractors/anthropic.py`: `_VALID_STOP_REASONS` frozenset; `_RefusalError`
and `_NoStructuredOutputError` exceptions. `extract_one` raises `_RefusalError` on
an untrusted `stop_reason` and `_NoStructuredOutputError` when `parsed_output is
None` — both before a `JobExtract` is built. `run()` catches both, logs, and
increments `stats.refused` / `stats.no_output`. Closed by #53 (+ `_NoStructuredOutputError` from #57).

### C2 — Import-time DB engine / settings — VERIFIED (closed)
`src/jmi/db/base.py`: no module-level `engine = _make_engine()`; `get_engine()`
is lazy and `@lru_cache`d. `src/jmi/config.py`: `get_settings()` is `@lru_cache`d;
`database_url` has no hardcoded default and a validator fails loudly if unset.
Closed by #56.

## High

### H2 — CLI / health-check error handling — VERIFIED (closed)
`cli.py` catches `RuntimeError` (missing API key) and `OperationalError` (DB
unreachable) with friendly messages; `analyze` catches
`(ValueError, OperationalError, RuntimeError, OSError)`. `/api/health` returns
HTTP 503 when the DB check fails (`api/routes/health.py`). Closed by #55.

### H3 — Ingest API hardening — VERIFIED (closed)
`api/auth.py` uses `hmac.compare_digest`; `api/schemas.py` bounds batch lists
(`_MAX_BATCH_ITEMS = 500`) and description strings (`_MAX_DESCRIPTION_CHARS =
500_000`); `config.py` has no hardcoded DB password and fails loudly if
`DATABASE_URL` is unset. Closed by #54.

### H4 — Repository pattern ambiguity — VERIFIED (closed)
`src/jmi/storage/base.py` (the unused `AbstractRepository`) is deleted. Canonical
pattern settled: concrete repository classes in `storage/`, Protocol-narrowed
slices at injection boundaries in `evaluation/runner.py` (documented, per
ADR-0010). Closed by #56.

### H6 — Stale docs — VERIFIED (closed)
`CLAUDE.md` no longer says "JustJoinIT OFF the table" — it describes JJIT as an
active HITL source (ADR-0009). `docs/roadmap.md` "Current state" records Phase 2
as merged (#20).
*Minor residual:* `roadmap.md`'s Phase 2 body prose still reads as future work
("Next PR: PR18") — outside H6's specific scope, but worth a small cleanup.

### H7 — Phase 3 observability conventions — PARTIAL (designed, not implemented)
The conventions are now binding constraints in `docs/phase3-design-constraints.md`
§3 (#52): per-stage `duration_ms` (O-1), `cost_usd_estimate` (O-2), durable
eval-run history (O-3), a `{domain}.{action}[.{outcome}]` structlog naming
convention (O-4), request-scoped `request_id` binding (O-5). None are implemented
in code yet (no `request_id` binding in `logging.py`/`api/app.py`, no stage
timing, no cost tracking). Deferred to Phase 3 PRs per the document's acceptance
criteria — expected state.

### H1 — Phase 3 personal-data security prerequisites — NOT STARTED (open by design)
Phase 3 has not started; none of the five prerequisites (corpus path sandboxing,
no logging of achievement content, purgeable personal-embeddings table,
prompt-injection canary, auth on Phase 3 endpoints) exist yet. The audit scoped
H1 as "design into PR-3.1/3.2/3.4" — to be addressed when Phase 3 PRs are written.

### H5 — Retrieval-evaluation infrastructure — NOT STARTED (open by design)
None of `evaluation/retrieval_metrics.py`, `docs/ground_truth/rag_retrieval_seed.json`,
deterministic embedding fixtures, or a shared `tests/fakes.py` exist. The
evaluation package still measures extraction quality only. Phase 3 infrastructure;
the audit acknowledged it as pre-Phase-3 work.

## Dev tooling baseline checklist — 7 / 7

| # | Item | Status |
|---|---|---|
| 1 | uv (`uv_build` backend, `uv.lock`) | VERIFIED |
| 2 | pre-commit (`.pre-commit-config.yaml`, ruff + hygiene hooks) | VERIFIED |
| 3 | ruff format (`[tool.ruff.format]`; `ruff format --check` clean) | VERIFIED |
| 4 | mypy strict (`strict = true`; `mypy src/` 0 errors) | VERIFIED |
| 5 | no `from __future__ import annotations` in `src/` (0 occurrences) | VERIFIED |
| 6 | Python >= 3.12 (`requires-python = ">=3.12"`) | VERIFIED |
| 7 | CI (`.github/workflows/ci.yml`; last runs green) | VERIFIED |

## Follow-ups (not regressions)

- **H1, H5** — to be built as part of Phase 3 (PR-3.x).
- **H7** — implement the documented O-1…O-5 conventions during Phase 3 PRs.
- **roadmap.md** — minor: Phase 2 body prose still reads as future work.
- Medium/Low audit items (M1–M11, L1–L10) were out of scope for this pass.

---
*Generated 2026-05-19 by a 4-sub-agent verification pass against `main` `8ed9c37`.*
