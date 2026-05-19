# Achievement Vault Template

This folder is a **template** for the personal-achievement corpus that the
Phase 3 RAG résumé generator retrieves from. It is not real data: the six files
under `_meta/career/achievements/` are generic **example shapes**, one per
common kind of achievement, for you to copy and rewrite with your own career
history.

## What this is

Each `.md` file under `_meta/career/achievements/` is one **achievement** — a
unit of career history the résumé generator can draw on. `jmi ingest-achievements`
parses these files into Postgres (the `achievements` table). See
[ADR-0014](../adr/0014-achievement-domain-schema.md) for the schema rationale
and `src/jmi/models/achievement.py` for the authoritative field definitions.

## The example files

Six samples ship here, each a different shape of achievement:

- `backend-service-production.md` — a backend system run in production.
- `data-pipeline-batch.md` — an ETL or batch data pipeline.
- `open-source-contribution.md` — a non-trivial open-source contribution.
- `university-capstone.md` — a university software-engineering project.
- `hackathon-project.md` — a time-boxed hackathon build.
- `jmi-flagship-project.md` — JMI itself, as an example of a portfolio project.

None of them describe a real person. Use them as starting shapes: rewrite the
ones that fit your history, and delete the ones that do not.

## How to use it

1. Copy `_meta/career/achievements/` into your real Obsidian vault — anywhere;
   ingestion finds achievement files by frontmatter, not by location.
2. Edit each file into a real achievement: replace every `[TODO: ...]`
   placeholder with specific detail, and rewrite the generic scaffolding
   sentences to describe what you actually did. The samples carry no real
   facts — they only demonstrate the shape of each section.
3. Point JMI at your vault, either with the `ACHIEVEMENTS_VAULT_PATH`
   environment variable or per run:
   `jmi ingest-achievements --vault-path /path/to/vault`.
4. Re-run `jmi ingest-achievements` whenever you edit a file. Ingestion is
   idempotent: existing rows are updated in place, matched by file path.

## File format

Each achievement file has two parts.

**YAML frontmatter** — metadata between `---` fences:

| Field | Meaning |
| --- | --- |
| `type` | Must be `achievement` — this is how ingestion recognises the file. |
| `title` | Short achievement name (max 200 characters); must be unique. |
| `skills` | Free-form skill tags. |
| `tech_stack` | Technologies used. |
| `seniority_relevance` | Any of `junior`, `mid`, `senior`. |
| `impact_metrics` | Quantified, free-form outcome statements. |
| `keywords` | Extra terms to boost retrieval. |

**Body** — four Markdown sections, each parsed into one field:

- `## Context` — the situation and your role.
- `## Approach` — what you actually did.
- `## Impact` — the concrete outcome.
- `## What I learned` — an honest reflection.

A file is ingested only if its frontmatter sets `type: achievement`. Any other
`.md` file — this README included — is skipped.

## Adding a new achievement

Copy any file under `_meta/career/achievements/` to a new `.md` file, keep the
frontmatter keys and the four `##` headings, and fill them in. The filename is
up to you; a short kebab-case slug of the title reads best.

## A note on privacy

This corpus is personal data. JMI keeps it in its own database tables, never
logs the body text, and never commits database backups (see ADR-0014). Keep
your real achievement files in your own Obsidian vault — do not commit them
into this repository.
