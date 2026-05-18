# Competitive Landscape

Research date: 2026-05-15 (Grok deep-research) + 2026-05-17 (verification web search).

## Why this document exists

Building in vacuum is anti-pattern. JMI must be positioned against existing work —
what's been done, what's missing, where JMI's unique value lies. This document is
reviewed before any major positioning decision (CV, LinkedIn, blog posts, talks).

## Closest comparable projects (GitHub)

### alexeygrigorev/ai-engineering-field-guide

- ~3.3k stars, active 2026 commits
- Data-driven analysis of 2,445 AI engineering job descriptions from builtin.com
- Includes interview process research, take-home challenges, learning paths
- Author: Alexey Grigorev (DataTalks.Club, ex-OLX, well-known in MLOps community)

Overlap with JMI: Job description analysis at scale, market intelligence.

What it does BETTER:

- Massive sample (N=2,445)
- Multi-city coverage (LA, NY, London, Amsterdam, Berlin, India)
- Publication scale + community traction
- Interview-focused content (rare quality)

What JMI does BETTER:

- Personal continuous pipeline (vs. one-shot analysis)
- Evaluation framework with per-field metrics
- Polish AI/ML niche (zero coverage in alexey's data)
- HITL Chrome extension architecture (ToS-clean)
- RAG resume gen planned (none in alexey's project)
- ADR-documented decisions throughout

Verified 2026-05-17: repo at github.com/alexeygrigorev/ai-engineering-field-guide

### BjornMelin/ai-job-scraper

- ~31 stars (per Grok)
- Privacy-focused, local-first Python
- ScrapeGraph-AI + LLMs + LangGraph agents
- SQLite storage, Streamlit dashboard

Overlap: AI/ML focus, LLM extraction, local-first design, dashboard.

What it does BETTER:

- Production-ready agentic scraping/filtering
- Streamlit polish

What JMI does BETTER:

- ToS-clean Chrome MV3 HITL (vs scraping)
- Evaluation framework with measurable metrics
- Polish portals coverage
- Custom RAG planned vs LangGraph (depth signal)
- Structured per-field metrics (Jaccard, salary recall)

### DEENUU1/job-scraper

- ~26 stars
- Python + Docker
- Polish portals: JustJoinIT, NoFluffJobs, BulldogJob, Pracuj.pl + international
- Google Sheets / SQLite / XLSX output

Overlap: Polish multi-portal ingestion.

What it does BETTER:

- Broader Polish coverage (4 portals vs current 2)

What JMI does BETTER:

- LLM structured extraction (none in their pipeline)
- Evaluation framework
- HITL pattern (ToS-clean, theirs is scraping)
- Planned downstream RAG/agent layers

Note: portal breadth is steal-worthy. Future PRs may add BulldogJob + Pracuj.pl.

## Commercial products (different category)

### CzyJestEldorado.pl

- Polish IT job aggregator (multi-portal, salaries, tech trends)
- Beta MCP server at https://czyjesteldorado.pl/_mcp
- Free for candidates, monetized via employer ads
- Strong UI, big traffic

Overlap with JMI: Polish market intelligence.

JMI advantage: Personal LLM extraction pipeline, custom RAG planned, HITL agent,
Postgres ownership, evaluation framework. Aggregator does not provide personal tooling.

Note: their MCP beta is interesting — JMI could expose own MCP server in Phase 4-5 for
Claude integration (different niche: personal data, not aggregated public data).

### Jobright.ai

- AI copilot: matches, tailored resume, autofill applications, tracker
- Freemium ~$30/mo
- Strong overlap on extraction/tailoring/agent

JMI advantage: ToS-clean ingestion vs their auto-apply (often ToS-violating), Polish
niche depth, custom RAG vs black-box, full data ownership.

### LazyApply, Sonara, Massive

Auto-apply tools. Often ToS-violating (resume sprayed across many platforms). JMI uses
HITL by design — user approves every submit per ADR-0009.

### Rezi, Teal, Final Round AI, Kickresume

Resume generators. Good at tailoring but no full ingestion + intelligence pipeline.
JMI scope is broader (system, not tool).

### Otta, Wellfound (AngelList), Levels.fyi

Job aggregators + salary data. Better distribution but no personal AI pipeline.
Different category.

## Where JMI fits

**Niche:** Polish AI/ML personal intelligence with engineering rigor.

**Unique combination (per 2026-05-15 research):**

1. ToS-clean Chrome MV3 HITL ingestion (rare)
2. Evaluation framework with measurable metrics (rare in personal projects)
3. Polish portal focus + custom RAG planning (rare combination)
4. ADR-documented decisions throughout (rare in side projects)

**Uniqueness assessment:** 60-70% (per Grok competitive analysis).

- Core ideas (ingest/extract/RAG/agent) overlap 40-50% with existing projects
- Evaluation rigor + ToS discipline + Polish niche + planned RAG/agent integration =
  the differentiator
- Execution quality determines perceived uniqueness

## Key insight from Alexey's research (verified 2026-05-17)

_(Alexey analyzed 2,445 job descriptions total, with an 895-job AI-First subset used for skills demand percentages.)_

From his analysis of 895 job descriptions (Jan 2026):

- **Evaluation is the differentiator** — 39.6% of AI-First roles explicitly require
  evaluation skills (LLM-as-judge, golden datasets, hallucination detection)
- "Anyone can build a chatbot — companies hire people who can measure if it works"
- Top skills demand: Python (82.5%), AWS (40.1%), RAG (35.9%), Docker (31.0%), evaluation (39.6%)
- AI Engineer is full-stack role: 93.1% need skills BEYOND just GenAI; only 1.4% expect pure GenAI work
- Fine-tuning is overhyped: only 4.0% of roles focus on it; 80.8% don't mention it

**Direct alignment with JMI work:**

- PR16 evaluation framework hits the 39.6% differentiator skill explicitly
- Python ✓, RAG planned ✓, Docker ✓, evaluation ✓ — 4 of 5 top skills already demonstrated or planned
- Missing from current scope: AWS deployment (Phase 5)

## What to steal / learn from competitors

| From | Idea | Action |
|---|---|---|
| alexeygrigorev | Scale-based skills demand analysis | Future PR: skills frequency dashboard from JMI extracts |
| alexeygrigorev | Interview process research | Long-term: document JMI interview prep with own data |
| BjornMelin | Privacy-first framing | README emphasizes local-first, data ownership |
| BjornMelin | Streamlit dashboard alternative | Phase 5 enhancement option vs static HTML |
| DEENUU1 | Polish portal breadth | Future PR: add BulldogJob + Pracuj.pl portals |
| CzyJestEldorado | MCP server pattern | Phase 4/5: expose JMI as MCP server for Claude users |
| Janvi Kalra | "From SWE to AI Engineer 46 interviews" narrative | When applying: document journey systematically |

## Honest assessment for positioning

1. **Not novel as concept** — job scrapers + LLM extraction + resume tools all exist
2. **Novel as combination + execution** — JMI's specific intersection (ToS-clean +
   Polish + eval framework + custom RAG) has no direct competitor
3. **Differentiation lives in execution quality** — measurable eval results, deep
   Polish insights, clean architecture, documented decisions
4. **Risk:** without strong demo metrics or insights, looks like another generic job
   tool. Must emphasize what's measurable.

## Positioning framework for CV/LinkedIn/portfolio

**One-liner:**

"Personal AI/ML job market intelligence system for Polish market — ToS-clean
architecture, evaluation framework, custom RAG planned."

**Three-sentence pitch:**

"Built a personal AI job market intelligence pipeline for Polish AI/ML roles. Ingests
AI/ML job postings from three sources (HuggingFace Jobs via official Workable API;
JustJoinIT and NoFluffJobs via ToS-clean Chrome MV3 HITL extension — webclipper pattern,
no scraping) and uses Claude Opus 4.7 with prompt caching and Pydantic structured outputs
to extract per-field data (seniority, tech_stack, salary, remote_policy). Includes
evaluation framework measuring per-field accuracy (Jaccard, salary recall) — the
eval-driven approach Alexey Grigorev's research shows is the #1 differentiator in AI
Engineer hiring."

**Skill demonstration matrix:**

- Python — entire backend
- LLM API integration — Anthropic SDK with prompt caching, structured outputs (Pydantic)
- RAG (planned Phase 3) — custom implementation, then LangChain comparison
- Docker — Compose for dev environment
- Prompt engineering — system prompt versioning, few-shot examples, iteration plan
- Evaluation — Jaccard similarity, salary recall, per-field metrics, ground truth schema (PR16)
- Database — Postgres 15 + pgvector + Alembic migrations
- Frontend — Chrome MV3 extension (background SW, offscreen DOMParser, popup, options)
- Testing — pytest 80 + vitest 89, real-DB tests for repos, fakes for evaluation runner

## References

- https://github.com/alexeygrigorev/ai-engineering-field-guide (verified 2026-05-17)
- https://github.com/alexeygrigorev/ai-engineering-field-guide/blob/main/role/02-skills.md (skills demand data)
- BjornMelin/ai-job-scraper (per Grok, not verified)
- DEENUU1/job-scraper (per Grok, not verified)
- https://czyjesteldorado.pl/_mcp (MCP server beta)
- Grok competitive analysis transcript 2026-05-15 (in JMI personal handbook, not committed to repo)

## Update protocol

Re-validate every 2-3 months:

- New competitors emerge
- Existing repos may pivot or die
- Market skills demand shifts
- JMI features change differentiation calculus

Last validated: 2026-05-17.
