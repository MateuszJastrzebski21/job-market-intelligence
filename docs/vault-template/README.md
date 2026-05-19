# Achievement Vault Template

This folder is a **template** for the personal-achievement corpus that the
Phase 3 RAG résumé generator retrieves from. It is not real data: the six files
under `_meta/career/achievements/` are AI-drafted starting points for you to
edit into accurate achievements.

## What this is

Each `.md` file under `_meta/career/achievements/` is one **achievement** — a
unit of career history the résumé generator can draw on. `jmi ingest-achievements`
parses these files into Postgres (the `achievements` table). See
[ADR-0014](../adr/0014-achievement-domain-schema.md) for the schema rationale
and `src/jmi/models/achievement.py` for the authoritative field definitions.

## How to use it

1. Copy `_meta/career/achievements/` into your real Obsidian vault — anywhere;
   ingestion finds achievement files by frontmatter, not by location.
2. Edit each file: replace every `[TODO: ...]` placeholder with real, specific
   detail. The drafts are roughly 80% plausible scaffolding and 20%
   placeholders — treat the non-`TODO` text as a suggestion, not as fact, and
   correct anything that is wrong.
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
