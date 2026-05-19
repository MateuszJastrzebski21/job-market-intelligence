# ADR-0014: Achievement Domain Schema — Personal-Corpus Storage for Phase 3 RAG

**Status:** Accepted
**Date:** 2026-05-19
**Context of:** the `Achievement` domain (`src/jmi/models/achievement.py`), the
`achievements` + `achievement_embeddings` tables, and Obsidian-vault ingestion (PR-3.1)

## Context

Phase 3 builds a RAG résumé generator (`docs/roadmap.md`). Its retrieval corpus
is the operator's personal career history — 15–20 hand-written Markdown files in
an Obsidian vault — not public job postings. PR-3.1 is the first sub-PR: it adds
the data layer (domain model, ORM, repository, Alembic migration) and a
`jmi ingest-achievements` command that parses vault Markdown into Postgres. It
makes no LLM calls and generates no embeddings — chunking, embeddings, retrieval,
and generation are PR-3.2 and PR-3.4.

This is the first time JMI stores personal data, so PR-3.1 is bound by the H1
security constraints of `docs/phase3-design-constraints.md` (audit issue #24).
That document's acceptance criteria name PR-3.1's deliverables explicitly:
"PR-3.1 ships S-1, S-2, S-3 and the `achievement_embeddings` table."

## Decision

**Add a dedicated `Achievement` domain — a Pydantic model, a repository, and two
tables — mirroring the existing `JobPosting` domain.** ADR-0006's separated
pipeline and ADR-0012's inline-Protocol repositories carry over unchanged:
ingestion writes `Achievement` rows; downstream RAG (PR-3.2) reads them.

1. **Two tables, not one.** `achievements` holds content and metadata;
   `achievement_embeddings` holds chunk-level vectors (`achievement_id` FK,
   `chunk_index`, `chunk_text`, `embedding vector(384)`). PR-3.1 creates
   `achievement_embeddings` empty — the chunking + embedding pass that fills it
   is PR-3.2. Design-constraints S-3 mandates a dedicated `achievement_embeddings`
   table; and because RAG retrieves *chunks*, a single document-level embedding
   column on `achievements` would be the wrong granularity and force a migration
   in PR-3.2. `vector(384)` matches the `all-MiniLM-L6-v2` dimensionality of
   ADR-0011.

2. **`slug` is a computed field.** It is derived from `title` by a Pydantic
   `@computed_field`, so it can never drift from the title. The ORM stores the
   computed value (under a UNIQUE constraint); the ORM→domain mapper never echoes
   a stored slug back — it re-derives from the title.

3. **`source_path` is stored vault-relative.** The model holds the path relative
   to the vault root, never an absolute path: machine-absolute paths never reach
   the database or the logs, and a relative path is a stable, portable upsert
   key. It also carries the table's second UNIQUE constraint.

4. **`lessons` is a fourth body field.** Alongside `context` / `approach` /
   `impact`, the `## What I learned` section is parsed into a `lessons` field so
   that section's content is not silently dropped on ingest.

5. **Markdown + YAML frontmatter, with a `type` discriminator.** One file per
   achievement: YAML frontmatter for metadata, `## Context / ## Approach /
   ## Impact / ## What I learned` for the body. A file is treated as an
   achievement only when its frontmatter carries `type: achievement`, so
   ingestion is agnostic to vault layout and skips ordinary notes. Frontmatter is
   parsed with `pyyaml`'s `safe_load`.

6. **Configuration.** The vault root is the `ACHIEVEMENTS_VAULT_PATH` environment
   variable (pydantic-settings), overridable per run by
   `jmi ingest-achievements --vault-path`. `docs/phase3-design-constraints.md`
   refers to this root conceptually as `ACHIEVEMENTS_DIR`; the implemented
   setting is `ACHIEVEMENTS_VAULT_PATH`, recorded here per that document's rule
   that any deviation is captured in an ADR.

## Security

H1 (`docs/phase3-design-constraints.md` §1, audit #24) is discharged as follows.

- **S-1 — path-traversal sandbox.** `ingest_vault` resolves every candidate file
  with `Path.resolve()` (collapsing `..`, following symlinks) and rejects — with
  a structured `achievement.ingest.rejected` log event — any path that is not
  `is_relative_to()` the resolved vault root, *before the file is opened*. A
  symlink inside the vault that points outside it is therefore never read.
  `Achievement.source_path` additionally rejects absolute paths and `..`
  components as defense-in-depth.

- **S-2 — no personal content in logs.** Ingestion logs file paths, a count
  summary, and at most titles — never the `context` / `approach` / `impact` /
  `lessons` body text. On a parse failure the ingestor logs the exception *type
  name* only; it deliberately does not log `ValidationError.errors()` (a
  divergence from the `scrape.skip.invalid` event), because Pydantic error
  payloads echo the offending input values — i.e. personal content.

- **S-3 — separate, purgeable storage.** `achievements` and
  `achievement_embeddings` are their own tables, with no foreign key to and no
  shared table with `job_postings` (ADR-0011). The documented purge path is this
  PR's Alembic migration `downgrade()`: it drops `achievement_embeddings` then
  `achievements`, removing every personal vector and source row without touching
  job data. `.gitignore` additionally excludes local database dumps so a backup
  carrying personal data cannot be committed.

S-4 (indirect prompt injection) and S-5 (auth on retrieve / generate endpoints)
are out of scope for PR-3.1 — it makes no LLM calls and exposes no HTTP endpoint
— and land with PR-3.4 per the design document.

Observability follows the H7 / O-4 event-naming convention
`{domain}.{action}.{outcome}`: PR-3.1 emits `achievement.ingest.done`,
`achievement.ingest.invalid`, and `achievement.ingest.rejected`.

## Consequences

### Positive

- Personal data lives in two tables that drop independently of job data —
  privacy and purgeability are structural, not procedural.
- `achievement_embeddings` is RAG-ready: PR-3.2 adds chunking and embeddings with
  no schema migration, and retrieval-evaluation metrics (H5) can rank durable
  chunk identifiers.
- Ingestion is idempotent (upsert keyed on `source_path`) and layout-agnostic
  (the `type: achievement` discriminator), so the operator can re-run it freely
  and organise the vault however they like.

### Negative

- PR-3.1 ships an `achievement_embeddings` table and `AchievementEmbeddingORM`
  with no code that writes them yet — a deliberate "schema ahead of behaviour"
  so PR-3.2 needs no migration.
- `slug` uniqueness is global: two achievements whose titles slugify identically
  collide on insert. Accepted — the operator owns a small vault and controls
  titles, and the collision surfaces as a clear database error.
- The upsert key is `source_path`, so renaming a vault file orphans its old row;
  a stale row is cleared by a manual delete or a full re-ingest.

### Neutral

- One new declared dependency, `pyyaml` (plus the `types-pyyaml` stub) — already
  present transitively, now a direct dependency.
- Achievement bodies are stored as raw Markdown text; the chunking strategy is
  intentionally deferred to PR-3.2.

## Alternatives Considered

a. **A single table union with `job_postings`.** Plus: one embeddings table, one
   repository, one code path. Minus: forces personal and public data to share
   storage and lifecycle — purging personal data becomes row-level deletes
   against a mixed table, and a job-data backup carries personal data; the two
   domains also share almost no columns. When: never — design-constraints S-3
   forbids it outright.

b. **A single document-level `embedding` column on `achievements`.** Plus: one
   table, the simplest possible PR-3.1 schema. Minus: RAG retrieves and ranks
   *chunks*, not whole documents; a document-level column cannot hold per-chunk
   vectors and would be dropped and replaced by a chunk table in PR-3.2 — a
   wasted migration — and it reads, against S-3, as embeddings on the content
   table. When: only if retrieval were ever whole-document, which it is not.

c. **The `python-frontmatter` library for parsing.** Plus: purpose-built; splits
   the fences and body in one call. Minus: an extra dependency whose whole job is
   a ~10-line split; the project favours small custom code over framework
   dependencies (the same reasoning as custom RAG over LangChain). When:
   reconsider if frontmatter handling ever grows non-trivial.

d. **Ingest only a fixed vault subdirectory.** Plus: no per-file type check.
   Minus: dictates the operator's vault layout. The `type: achievement`
   frontmatter discriminator is layout-agnostic and costs nothing. When: rejected.

## References

- `docs/phase3-design-constraints.md` — H1 (S-1, S-2, S-3), the PR-3.1
  acceptance line, and the H7 / O-4 event-naming convention.
- `docs/audit-2026-05-18.md` — issue H1 (#24), the personal-data security
  prerequisites this ADR discharges.
- [ADR-0006: Extraction Pipeline Architecture](0006-extraction-pipeline-architecture.md)
  — the separated ingest / downstream pipeline the Achievement domain follows.
- [ADR-0011: Phase 2 Analytics PoC](0011-phase2-poc-choices.md) — the
  `all-MiniLM-L6-v2` / `vector(384)` embedding choice reused for the chunk table.
- [ADR-0012: Repository Pattern — Inline Protocols](0012-repository-pattern-protocol.md)
  — the inline-`Protocol` repository pattern the ingestor's `AchievementWriter` uses.
- `docs/roadmap.md` — the Phase 3 sub-PR breakdown.
