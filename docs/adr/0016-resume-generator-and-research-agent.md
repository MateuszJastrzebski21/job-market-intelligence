# ADR-0016: Resume Generator + Smart Cover Letter Research Agent (PR-3.4)

**Status:** Accepted — pending PR-3.4 merge.

**Date:** 2026-05-21

**Context of:** the `jmi generate-resume` command and its three new packages
— `src/jmi/resume/`, `src/jmi/cover_letter/`, `src/jmi/research/` — plus the
`tailored_resumes` and `company_research_cache` tables.

**Companion documents:**
`.claude/worktrees/jmi-pr34-research/docs/research/pr-3.4-resume-generator-dossier.md`
(internal pre-implementation dossier, May 2026; every decision below traces
back to a numbered section there). ADR-0014 (Achievement domain),
ADR-0015a (custom RAG that PR-3.4 consumes), ADR-0005 (structured outputs),
ADR-0011 (Phase 2 embedding choices), `docs/phase3-design-constraints.md`.

---

## Context

PR-3.4 closes the loop on JMI's RAG thesis: it turns the just-merged
retrieval stack (PR-3.2 custom RAG; PR-3.3 LangChain mirror, MRR 0.878 vs
0.906 — statistically indistinguishable) into a single command that an
operator can run against a real JD and walk away with markdown bullets and
a cover letter whose first sentence references a SPECIFIC fact discovered
about the company at generation time, not at templating time.

Original roadmap split bullets (PR-3.4) from cover letter (PR-3.5). The
dossier collapses them into one PR because the orchestration overhead of
the second sub-PR exceeded the incremental scope: bullets + cover letter
both consume the same retrieved chunks, both run under the same DB session,
both want to land in one audit-trail row. The dossier also identifies the
smart cover letter agent — `Anthropic web_search` driven, synchronous, per
generation — as the single most defensible portfolio differentiator
(market scan: no commodity tool does this at generation time; see §2 of
the dossier for evidence).

This ADR records ten decisions PR-3.4 pinned and why. It is the
implementation contract; the dossier is the broader research record.

## Decisions

### D-1. Two-call research architecture (no `tools=[web_search]` + `messages.parse`)

`src/jmi/research/company_agent.py` runs research in TWO LLM calls:

- **Call 1:** Opus 4.7 + `messages.create(tools=[web_search_20250305])`.
  Returns unstructured prose with inline source URLs.
- **Call 2:** Sonnet 4.6 + `messages.parse(output_format=CompanyResearch)`.
  Pure transformer — no web access — synthesises Call 1's text into the
  schema.

**Why** — operator-resolved Q3 + dossier §4. Combining `tools=[web_search]`
with `messages.parse(output_format=...)` is under-tested in our codebase;
the dossier flags an analogous incompatibility (`citations` + structured
outputs returns a 400). The split lets each call have one job. Cost
overhead is ~$0.013 per generation (Sonnet 4.6 synthesis call) — acceptable
in exchange for reliability.

**Alternative considered.** Single `messages.parse(tools=[web_search],
output_format=CompanyResearch)`. Rejected as the primary path because (a)
the SDK 0.96 type stubs don't list `web_search_20250305` as a valid tool
union variant, (b) the dossier explicitly flags an analogous structured-
outputs + tool-use incompatibility, and (c) when the combination silently
mis-fires, the failure mode is opaque (no structured output → caller can't
distinguish "tool ran but synthesis failed" from "tool errored"). The
two-call split makes each failure surface clean.

### D-2. `web_search_20250305` over Tavily / Brave / Perplexity Computer

`src/jmi/research/company_agent.py` uses Anthropic's first-party
`web_search_20250305` server tool, capped at `max_uses=3` by default
(`--research-depth {1,3,5}` overrides).

**Why** — dossier §4. The server tool is fully managed (Claude decides
when to search and chains queries server-side; returns citations; one HTTP
round-trip from our process). Tavily/Brave would mean an extra dependency
+ a separate API key + manual chaining logic we'd have to write. Perplexity
Computer is $200/month and overkill for one company at a time. The
$10-per-1000-search fee is negligible at expected operator volume.

**Alternative considered.** Tavily REST API with our own orchestration
(dossier §4 multi-step planner pattern). Rejected — wrong size of tool for
a single-company, three-search lookup. Revisit only if `web_search` is
shown to be too noisy / too low-recall in the eval harness.

### D-3. Structured outputs without native citations

`StructuredBulletGenerator`, `CoverLetterGenerator`, and the JD parser all
use `messages.parse(output_format=...)`. None enables Anthropic's native
`citations` feature.

**Why** — dossier §3. The Anthropic docs are explicit: citations + an
`output_format` schema returns 400. Chunk-id provenance therefore flows
through the schema itself: each `ResumeBullet` carries `chunk_ids:
list[str]`, each `CoverLetterParagraph` carries `chunk_ids:
list[str]`. A post-hoc validator
(`src/jmi/resume/bullet_validator.py`) checks every cited
chunk_id is in the retrieved set.

**Alternative considered.** Manual JSON parsing via `messages.create` +
`model_validate_json` on the result text. Rejected — schema-grammar
guarantees from `messages.parse` are worth the constraint of not
enabling native citations.

### D-4. Per-company TTL cache at 7 days

`src/jmi/storage/company_research_cache.py` stores serialised
`CompanyResearch` keyed by `SHA256(normalised company_name + '|' +
domain)`. Default TTL 7 days, enforced application-side in
`CompanyResearchCacheRepository.get(..., ttl_days=7)`. Operator bypasses
with `--refresh-research`.

**Why** — dossier §7. An AI Engineer applying to 5 roles at the same
company over 2 weeks should get one research call, not five — saves
~$0.078 per repeat. 7 days strikes a balance: company "recent news"
material rarely shifts week-to-week, but stretching to 30 days risks
serving the operator a stale opener. Application-side enforcement (rather
than a DB constraint) lets the same row serve different effective TTLs by
different callers.

### D-5. `chunk_ids_used` as `TEXT[]` + GIN index, NOT a foreign key

`tailored_resumes.chunk_ids_used` is `TEXT[]` of stringified UUIDs
referring to `achievement_embeddings.id`, with a GIN index. Deliberately
not a foreign key.

**Why** — dossier §5 + operator-resolved Q5. Achievement chunks get
re-chunked when the operator edits or restructures a vault file (the
"delete then insert by `achievement_id`" upsert pattern from PR-3.2 — see
ADR-0014). A hard FK would either cascade-delete past audit-trail rows on
every re-chunk OR require a migration cascade. Array + GIN gives 95% of
the analytical value at 5% of the migration pain. The GIN index supports
`chunk_ids_used && ARRAY[…]` containment queries for "which generations
cited this chunk?".

### D-6. Markdown only — PDF deferred to Phase 5

`src/jmi/resume/formatter.py` emits markdown. No PDF rendering anywhere
in PR-3.4.

**Why** — dossier §1 + §8.4. ATS-system landscape for Polish AI Engineer
roles is unmapped; the operator's downstream rendering tool (Pandoc,
Typst, paste-into-LinkedIn) determines ATS behaviour today. Shipping PDF
in PR-3.4 commits to a renderer before we have data on what to optimise
for. Markdown is the universal source format; the formatter uses standard
"Selected Achievements" / "Cover Letter" headings (no emoji per the
Jobscan 2026 mistakes guide) so it survives most downstream conversions.

### D-7. Single-LLM-with-tool, not multi-step planner

Research is one Anthropic call (Call 1 above). No sub-agents, no
hierarchical decomposition.

**Why** — dossier §4 + §1 non-goals. Perplexity Computer's 19-model
hierarchical planner is the SOTA for deep-research products; for one
company per CLI invocation it is overkill. The single-LLM-with-tool path
(Cobus Greyling's observation in the dossier) "lets Claude chain multiple
searches intelligently without you scripting every step" while keeping
the implementation small enough that one operator can read and reason
about it.

### D-8. Verb-elevation rules enforced post-hoc, not in-prompt

`src/jmi/resume/bullet_validator.py` enforces a table of allowed verb
transitions (leadership claim verbs like "led" / "owned" / "managed"
require explicit chunk-text support; lateral verbs like "built" / "implemented"
pass on chunk membership alone). Violations trigger one retry with a
clarifying user message; still-invalid bullets are dropped from the output.

**Why** — dossier §3 + §8.3 (this is the single highest-risk failure
mode for the project's honesty-first positioning). In-prompt rules
("don't elevate scope") work most of the time but are not enforceable — a
model that violates them silently is the worst possible failure mode. A
post-hoc validator with a deterministic rule table makes the constraint
auditable and gives every operator-facing bullet a guarantee: every
leadership claim traces to a chunk that uses the leadership verb.

**Alternative considered.** Verb-elevation policed entirely in the system
prompt. Rejected — same reason ADR-0005 prefers structured outputs over
prompt-cajoling: post-validation catches what the prompt missed.

### D-9. `CompanyResearch.confidence == "low"` gates the cover-letter opener style

The cover-letter prompt (`src/jmi/cover_letter/prompts.py`) reads
`company_research.confidence` and switches the opener style: `high` /
`medium` → company-specific opener referencing a fact from
`recent_news` / `mission_or_thesis` / `tech_stack_signals`; `low` (or
research absent entirely) → role-specific generic opener with NO
fabricated specifics. The draft surfaces `company_specific_opener: bool`
so the formatter can render a low-confidence note inline.

**Why** — dossier §4 + §8.2. Obscure-company graceful degradation is the
distinguishing call between "smart" and "confidently wrong". Polish
boutique AI consultancies, stealth startups, and government agencies
will trigger low-confidence research; better a slightly bland letter
than a fabricated one. The hard split at the schema level rather than
in-prompt makes the behaviour testable.

### D-10. English-only cover letter in v1 (warning when language=pl)

`jmi generate-resume` detects `JobDescription.language == "pl"` and emits
a stderr warning ("Polish JD detected; English-only output in v1") but
proceeds. Polish-language output is deferred to PR-3.5.

**Why** — operator-resolved Q4 + dossier §10 Q4. Polish-style CVs follow
different conventions (no photo since 2020 GDPR shift, formal closing
register, sometimes a third-paragraph etiquette) which the v1 prompt
isn't designed for. The Talent Place 2025 guide notes English is broadly
acceptable for Polish tech roles, so the v1 trade-off is small. Tracking
the warning as project memory will help us evaluate frequency before
investing in Polish prompts.

---

## Persistence

`tailored_resumes` is append-only — every generation is a distinct audit
row. Retention is permanent (operator-resolved Q2); `jmi vault purge
--before DATE` is deferred to PR-3.5. The DB schema lives in the public
repo; the operator's actual generations stay local
(operator-resolved Q6).

`generation_duration_ms` is captured per row (operator-resolved Q7) for
internal unit-economics analysis. No external telemetry — the column
exists only for `psql`-driven analytics.

## Testing

PR-3.4's prerequisite commit (`PR-3.4-prep`) introduced testcontainers
fixtures (`tests/fixtures/postgres.py`): a session-scoped
`pgvector/pgvector:pg15` container with per-test transaction-rollback
isolation. Repo tests run against the real DB; Anthropic calls are
mocked with `FakeAnthropic` (`tests/fixtures/anthropic_responses.py`) at
the SDK contract level — two queues, one for `messages.create` (multi-block
tool_use payloads) and one for `messages.parse` (parsed Pydantic instances).
No `respx`, no recorded fixtures — assertions check what arguments were
passed (`tools=`, `cache_control`, `output_format`).

## Consequences

- **Scope:** PR-3.4 is one PR spanning six commits, ~33 files,
  ~3,500 LOC including tests and prompts.
- **Cost:** ~$0.167 per generation at list prices (dossier §7, revised
  to include the Sonnet 4.6 synthesis call per D-1). Per-company cache
  drives this to ~$0.089 on a cache hit.
- **Honesty discipline:** the verb-elevation validator + numeric grounding
  + chunk-id provenance + low-confidence fallback give every operator-facing
  output a defensible audit chain.
- **Future work flagged for PR-3.5+:** Polish-language output, `vault
  purge`, `--batch` mode, optional fine-tuning of the bullet stage, and
  the resume-quality eval framework (originally PR-3.7).
