# ADR-0013: Future-Import Removal + the UP037 Interdependency

**Status:** Accepted
**Date:** 2026-05-19
**Context of:** `from __future__ import annotations` handling across `src/jmi/`, and the ruff `UP037` pre-commit hook

## Context

PR #57 (the dev-tooling checklist) dropped `from __future__ import
annotations` across `src/jmi/`, moving the backend onto Python 3.12 eager
annotation evaluation instead of PEP 563 lazy evaluation. That removal is
coupled to ruff's `UP037` (`quoted-annotation`) rule: `UP037` strips quotes
from annotations it deems redundant, but a quoted forward reference is only
redundant *while* the future-import is present.

The coupling was learned the hard way. Splitting that work into separate
commits — the rejected "Phase B" on the `chore/dev-tooling-checklist` branch —
failed: the pre-commit `ruff check --fix` hook re-applied `UP037` to each
intermediate commit and unquoted the annotations mid-sequence. The change
shipped as one atomic commit (`1652a56`), whose message is the only prior
record of this rationale. This ADR makes it a standing convention.

## Decision

**Any change to a module's `from __future__ import annotations` status —
adding or removing it — must land in one atomic commit that also quotes or
unquotes every annotation whose validity depends on that import.** The
future-import line and its dependent quotes are one indivisible edit.

`src/jmi/` now carries no `from __future__ import annotations` and relies on
Python 3.12 eager evaluation. Three forward references that resolved only
under PEP 563 lazy evaluation are quoted so eager evaluation succeeds:

- `db/models.py` — `Mapped[list["JobExtractORM"]]`, a class defined lower in
  the same file;
- `analytics/embed.py` — `"SentenceTransformer"`, a `TYPE_CHECKING`-only
  import, at two sites;
- `sources/huggingface/client.py` — `__enter__` returning `"WorkableClient"`,
  a self-type named inside its own class body.

`UP037` stays enabled (the `UP` family in `[tool.ruff.lint]`) — it is correct
for every module that still carries the future-import.

### Scope

The convention applies to `src/` today, cleaned in PR #57. It applies
identically wherever a future-import is removed elsewhere — notably `tests/`,
where 24 files still carry `from __future__ import annotations`, deferred
under PR #57's `src/`-only scope. Follow it when that work happens.

## How to apply

1. **Find the forward references.** Remove the future-import in your working
   tree, then run an empirical import scan — walk the package with
   `pkgutil.walk_packages`, `importlib.import_module` each module, and collect
   the `NameError`s eager evaluation raises. Static analysis misses
   self-referential annotations such as `__enter__ -> "WorkableClient"`.
2. **Quote each forward reference** the scan reports.
3. **Commit atomically** — the quotes, the future-import removal, and the
   resulting `ruff format`, in one commit.
4. **Why atomic:** while the future-import is present, `UP037` deems the new
   quotes redundant, so a separate "add quotes" commit lets the pre-commit
   hook strip them before the removal lands.

**Anti-pattern:** do not trust static analysis alone to find forward
references — run the import scan, since the interpreter is ground truth.

## Consequences

### Positive

- The interdependency is discoverable — an ADR, not one line in `git log`.
- The split-commit race cannot recur; the convention forecloses it.
- `src/` has no PEP 563 dependency; annotations behave identically at runtime
  and under tooling.

### Negative

- A future-import change cannot be reviewed as a series of small commits; it
  is inherently one commit, large for a directory-wide change.

### Neutral

- A *stable* mixed state is fine — `src/` without the import, `tests/` with
  it; only a *transition* triggers the gotcha.
- CI runs `ruff` without `--fix`, so it fails a bad split rather than
  rewriting it — the race is local to the pre-commit hook.

## Alternatives Considered

a. **Split the change across commits (the rejected "Phase B").** Plus:
   smaller, individually reviewable commits. Minus: with the future-import
   still present, the hook's `UP037` strips forward-reference quotes from an
   earlier commit, so the removal lands on bare references and breaks. When:
   never, while the hook runs `ruff check --fix`.

b. **Disable `UP037`.** Plus: removes the coupling outright. Minus: forfeits a
   useful pyupgrade lint everywhere to defuse a problem that arises only on a
   future-import transition and is cheaply handled by an atomic commit. When:
   not warranted.

c. **Drop `--fix` from the pre-commit ruff hook.** Plus: the hook stops
   mutating files, so no commit can be raced. Minus: forfeits auto-fix for
   every other rule — the reason `--fix` is configured — for one rare
   interaction. When: only if hook rewrites cause recurring friction.

## References

- PR #57 (`chore: dev tooling checklist`) — commit `1652a56` did the
  atomic removal; its message is the original record of this rationale.
- The rejected "Phase B" split-commit attempt on branch `chore/dev-tooling-checklist`
  — the evidence that motivated this convention.
- `.pre-commit-config.yaml` — the `ruff check --fix` hook that races a split.
- `pyproject.toml` `[tool.ruff.lint]` — selects the `UP` family, enabling `UP037`.
