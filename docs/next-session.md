# Next session — Strategic foundation set (2026-05-17)

## Status after 3-day sprint (May 14-16, 16 PRs merged)

### Code base operational
- Phase 1 Week 1+2 complete: HF API scraper + JJIT HITL extension + NFJ HITL extension
- 16 PRs merged in 3 days (PR1-17), all squash-merged via GitHub
- Tests: 80 pytest + 89 vitest = 169 total, all green
- 5 ADRs documenting architectural decisions (separated pipeline, JJIT ToS pivot, HITL adoption, evaluation framework)
- pgvector + Postgres 15 + Alembic + structured logging operational

### Data state per machine
- **Mac (this session):** 18 jobs total (2 hf + 16 jjit), 7 LLM extracts via Claude Opus 4.7
- **PC (last session, 2026-05-15):** 57 jobs total (9 hf + 28 jjit + 20 nofluff), 24-30 extracts

### Strategic findings from PC sprint (preserved here)

## A. Quality investigation findings

Sample peek of 10 fresh JJIT extracts (PC, 2026-05-15) revealed quality breakdown:
- tech_stack: 8/10 (scales with description length, 10-15 items for detailed jobs, drops to 3-5 for short ones)
- seniority: 8/10 (mid/senior split sensible)
- remote_policy: 9/10 (capture good)
- salary: 2/10 — **CRITICAL BUG** (salary in description text but extracted as NULL)
- coverage: 5/10 (N=57 PoC, AI/ML niche only)

Specific bug example: "AI Engineer (middle)" job at RITS — description contains literally "Stawka: do 145 PLN/h" but Claude extract returned salary_min/max/currency=NULL.

Confirmed cross-portal: NFJ extracts (Data Scientist GenAI/LLM, Software Engineer Agent Dev) also show NULL salary despite "Stawka: do 150 PLN netto + VAT/h" and "Salary: 20 000 - 23 000 PLN gross/month" in source text.

## B. Few-shot examples revelation

`docs/ground_truth/phase1_seed.json` exists since 2026-04-22 (PR1 commit b35f679). Contains 3 HuggingFace job examples used dual-purpose:
1. Few-shot inputs in extractor system prompt (~4.4K tokens, above 4096 cache minimum)
2. Future ground truth for evaluation framework

**Existing labels are systematically under-extracted** (e.g., "AI for Robotics" labeled with tech_stack=[Python, PyTorch, Git] only — description mentions Hugging Face Hub, robotics frameworks, library refactoring patterns that should also appear).

This means: Claude extractor learned conservative tech_stack from biased few-shot examples. Salary captured as NULL in all 3 examples because HF jobs don't show salary — Claude generalizes "salary often null, default null when uncertain".

## C. PR17/PR18 sequence dependency

- **PR17 (prompt improvements)** requires ground truth labels for measurement. Without 30+ manually labeled JJIT/NFJ jobs in `phase1_seed.json`, prompt fixes are eyeballed, not measured.
- **PR18 (Phase 2 PoC)** works on existing extracts, doesn't need labels yet.
- **Therefore order:** PR18 first → labeling sprint (1.5h focused work, deferred to fresh day) → PR17 prompt fix → re-extract → measure delta vs baseline.

## D. Competitive landscape (Grok analysis + Alexey research)

Three closest comparable projects (per Grok 2026-05-15 + web verification):
- **alexeygrigorev/ai-engineering-field-guide** (3.3k stars) — Job descriptions analysis, 2,445 samples, interview research. Better at scale, worse on personal pipeline.
- **BjornMelin/ai-job-scraper** (~31 stars) — Privacy-first AI/ML scraper, LangGraph agents, Streamlit dashboard. Better at agent automation, worse on ToS compliance.
- **DEENUU1/job-scraper** (~26 stars) — Polish portal scraper (JJIT, NFJ, BulldogJob, Pracuj.pl). Better at portal breadth, worse on LLM extraction.

Commercial competitors: Jobright.ai ($30/mo AI copilot), CzyJestEldorado.pl (Polish aggregator with MCP beta), Otta/Wellfound (aggregators), Rezi/Teal (resume tools), LazyApply (auto-apply, often ToS-violating).

**JMI uniqueness assessment: 60-70%** (per Grok). Core ideas (scrape/extract/RAG) overlap 40-50% with existing; differentiators add the rest.

### Differentiation angles (use in CV/portfolio)
1. **ToS-clean Chrome MV3 HITL** — rare, most projects scrape (ToS violation)
2. **Evaluation framework with measurable metrics** — Jaccard, salary recall, per-field accuracy (rare in personal projects)
3. **Polish AI/ML niche** — almost zero competition in this specific intersection
4. **ADR-documented decisions** throughout — process discipline rare in side projects
5. **Custom RAG planned** (Phase 3) vs LangChain — depth understanding signal

### Key insight from Alexey's research (895 jobs analyzed)
- "Evaluation is the differentiator" — 39.6% AI-First roles explicitly require evaluation skills
- "Anyone can build a chatbot — companies hire people who can measure if it works"
- **PR16 evaluation framework directly aligned with market demand**

Top skills demand from his data: Python 82.5%, AWS 40.1%, RAG 35.9%, Docker 31.0%, evaluation 39.6%.

## E. PR15 NFJ findings + edge case

- 20 NFJ rows saved in single Save (Polish AI/ML jobs from /pl/backend)
- 19/20 with descriptions (95% capture rate)
- Polish UTF-8 chars verified (no mojibake)
- Tech_stack capture **deeper** for NFJ (16-17 items typical) than JJIT (10-12 items) — NFJ Angular SSR provides cleaner section structure (#posting-description, #posting-tasks etc.)

**Edge case (1/20):** Fullstack Developer at Square One Resources — description_html=0 AND description_text=0. Investigated: URL returns HTTP 200 but renders Angular `posting-not-found` template (employer withdrew posting between scrape and detail fetch). Parser behavior is correct (returns empty for missing selectors). Dead-row detection future scope.

## F. Project progress

- ~30% of original 16-week plan complete after 3 days
- ~15% of allocated time spent
- **2x velocity** vs original plan
- Realistic timeline to first AI Engineer offer: 6-8 weeks at current pace, 10-12 weeks at sustainable rhythm

## G. Strategic positioning (decided)

Reframe project narrative:
- **NOT** "another job scraper / aggregator"
- **YES** "production-grade personal AI Engineering demonstration that happens to ingest job postings"

Key messaging:
- ToS-clean architecture with ADR-documented decisions
- Evaluation rigor with measurable per-field metrics (eval-driven engineering loop)
- Polish AI/ML market intelligence (data advantage, niche)
- Decoupled replayable pipeline (separate scrape/extract per ADR-0006)
- Custom RAG planning (depth signal vs LangChain importer)

Update applies to: README.md (reframe in next pass), CV bullet points, LinkedIn About, future blog posts.

---

## Decision for tonight (2026-05-17, ~23:00)

**Path A — Strategic docs sprint** chosen. Three passes:
1. **Pass 1** (now): `docs/competitive-landscape.md` + this rewritten `docs/next-session.md`
2. **Pass 2** (next): README reframe ("Not another job scraper")
3. **Pass 3** (next): `docs/journal.txt` entry — May 14-16 retrospective

## Tomorrow's options (Monday)

After strategic foundation set tonight, Monday can be:
- **PR18 Phase 2 PoC** (~3h focused) — embeddings + clustering + dashboard
- **Save NFJ data on Mac** (40 min) + PR18 — broader data for analytics
- **Manual labeling sprint** (1.5h) — populate ground truth for future PR17

Recommended Monday flow: PR18 first (downstream pipeline demo), labeling deferred to Tuesday/midweek.

## Pre-flight checklist (every session)

```bash
cd ~/Desktop/job-market-intelligence
git fetch origin
git status                                    # confirm clean, in sync with origin
docker compose ps                             # postgres healthy
docker compose up -d                          # if down
pkill -f "jmi serve" 2>/dev/null
sleep 1
uv run jmi serve &
sleep 3
curl -s http://127.0.0.1:8000/api/health     # status:ok, db_ok:true
docker compose exec postgres psql -U jmi -d jmi -c \
  "SELECT source, count(*), count(description_text) AS filled FROM job_postings GROUP BY source;"
```
