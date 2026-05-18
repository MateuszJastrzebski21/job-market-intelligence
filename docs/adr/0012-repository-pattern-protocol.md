# ADR-0012: Repository Pattern — Inline Protocols, No Shared Base Class

**Status:** Accepted
**Date:** 2026-05-18
**Context of:** Repository abstractions across `src/jmi/` (storage, evaluation)

## Context

Two repository-typing styles coexisted. `src/jmi/storage/base.py` defined
`AbstractRepository(Protocol[T])` — a single generic base contract
(`add` / `get` / `list`) intended as the shared supertype for every repository.
Separately, `evaluation/runner.py` declares small, use-case-specific Protocols
(`PostingFinder`, `ExtractLister`) — each naming only the method slice that one
consumer actually calls.

The 2026-05-18 audit (#27 / H4) found `AbstractRepository` had **zero importers**
anywhere in `src/` or `tests/` — it was dead code. The two styles needed
reconciling into one documented convention.

## Decision

**Use inline `Protocol`s, declared per use site; no shared repository base class.**
`AbstractRepository` is deleted. Each module that consumes a repository declares
a local `Protocol` naming exactly the methods it uses — the pattern already in
`evaluation/runner.py`:

```python
class PostingFinder(Protocol):
    """The slice of JobPostingRepository the runner needs."""

    def get_by_source(self, source: str, source_job_id: str) -> JobPosting | None: ...
```

Concrete repositories (`JobPostingRepository`, `JobExtractRepository`) declare no
conformance — `Protocol`s are structural, so a repo satisfies a consumer's
Protocol simply by having the methods.

## Consequences

### Positive

- The contract lives next to the consumer and lists only what that consumer
  needs — the dependency surface is explicit and minimal at the use site.
- In-memory test fakes implement only the narrow Protocol, not a broad
  `add`/`get`/`list` base — which is how the existing repo fakes are already
  written.
- No dead generic abstraction to keep in sync with concrete repositories.

### Negative

- The same method signature may be declared in more than one Protocol when two
  consumers need the same slice. Accepted: a few duplicated one-line signatures
  are cheaper than one overgeneralized base everyone must conform to.

### Neutral

- Concrete repositories are typed nominally at their definition; Protocols are
  introduced only where a consumer wants a narrowed, swappable dependency.

## Alternatives Considered

a. **Keep `AbstractRepository(Protocol[T])` as a shared base.** Plus: one place
   to read "what is a repository". Minus: overgeneralizes — most consumers use
   one or two methods, not the full `add`/`get`/`list` surface; it had zero
   importers; a generic `Protocol[T]` reads less clearly at the use site than a
   concrete-typed local Protocol. When: reconsider only if a genuine need for
   uniform polymorphism over all repositories appears.

b. **Abstract base class (`abc.ABC`) instead of `Protocol`.** Plus: explicit
   registration. Minus: forces an inheritance edge on every concrete repo and
   every test fake; structural typing already gives the substitutability we
   want without the coupling.

## References

- [ADR-0006: Extraction Pipeline Architecture](0006-extraction-pipeline-architecture.md) — the separated-pipeline design these repositories serve.
- Issue #27 (audit H4) — flagged `AbstractRepository` as dead code.
- `src/jmi/evaluation/runner.py` — the `PostingFinder` / `ExtractLister` Protocols this ADR adopts as canonical.
