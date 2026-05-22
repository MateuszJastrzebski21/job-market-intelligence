# JMI Roadmap

Last updated: 2026-05-18. Reviewed weekly. Updates via PR.

## Compass

**Mission:** Production-grade personal AI Engineering demonstration via Polish AI/ML job
market intelligence pipeline. Portfolio flagship for AI Engineer role applications +
working personal tool.

**Anti-mission:** NOT another job scraper. NOT auto-applier spammer. NOT generic
dashboard for everyone.

**Target outcome:** AI Engineer offer at mainstream product company or AI-native
startup within 6-12 weeks of focused execution.

## Current state (as of last update)

- Phase 1: 95% done (3 portals: HF + JJIT + NFJ, all HITL/API ToS-clean)
- Phase 2: PoC merged (PR #20) — embeddings + clustering + market report
- Phase 3: next (RAG résumé generator) — design constraints documented
  (`docs/phase3-design-constraints.md`); Phase 4-5: 0%
- Tests: 117 pytest + 89 vitest = 206 green
- Coverage: ~57 jobs ingested on PC, ~18 on Mac (per-machine DBs)
- Velocity vs plan: 2x ahead

## Roadmap by phase

### Phase 2: Analytics PoC (Week 5-6 plan, NOW)

**Goal:** First downstream layer over Claude extracts. Demo-ready dashboard + shareable
markdown report.

**Next PR: PR18 — Phase 2 PoC**

- Embeddings via sentence-transformers all-MiniLM-L6-v2 (no Voyage key)
- pgvector storage (Alembic migration)
- KMeans clustering k=6 fixed (silhouette score logged, warn <0.2)
- HTML dashboard (Chart.js CDN, single file)
- Markdown report `docs/market-report-{date}.md`
- CLI: `uv run jmi analyze --output report.html`
- ADR-0011 documents PoC choices

**Pre-PR18 work:**

- Mac NFJ data save (~40 min, optional — can run on N=18 if rushed)
- All-extracts run: `uv run jmi extract -n 50`

**Estimated effort:** 3-4h focused. Single ride.

**Deferred to later in Phase 2:**

- N=200+ data acquisition (continued ingestion over weeks)
- Streamlit alternative dashboard (vs HTML)
- Real-time refresh capability
- Multi-source enrichment (BulldogJob, Pracuj.pl per DEENUU1 idea)
- Public GitHub Pages dashboard hosting

### Phase 3: RAG Resume Generator (Week 7-10 plan, ~6-8 weeks realistic)

**Goal:** Personal achievement RAG → tailored CV bullets + cover letters per offer.

**Largest phase by complexity** — biggest risk + biggest portfolio payoff.

**Sub-PRs:**

- PR-3.1: Achievement database schema + Obsidian/Markdown ingestion — **DONE**
- PR-3.2: Custom RAG implementation (no LangChain) — chunking, embeddings, retrieval — **DONE**
- PR-3.3: LangChain reimplementation for comparison (ADR-0015 documents tradeoffs) — **DONE**
- PR-3.4: Tailored resume generator + smart cover letter research agent — **DONE**
  (bullets + cover letter + Anthropic web_search company research collapsed
  into one PR; see [ADR-0016](adr/0016-resume-generator-and-research-agent.md))
- PR-3.5: `jmi vault purge` + Polish-language output + `--batch` mode
- PR-3.6: ATS-optimized PDF rendering (ReportLab or WeasyPrint)
- PR-3.7: Evaluation framework for resume quality (LLM-as-judge + manual A/B)

**Prerequisites:**

- Achievement database: 15-20 markdown files in personal Obsidian Career/ vault. User
  writes these manually (NOT scrapped, NOT generated).
- Examples needed: production work experience, a portfolio project, a quantitative or
  analytical project, a competition entry, a community/club involvement
- Eval ground truth: ~10 jobs with manually crafted "ideal CV" for measurement

**Senior signals demonstrated:**

- Custom RAG from scratch (depth understanding)
- Framework comparison via ADR (tradeoffs articulation)
- Evaluation rigor (resume quality measurable)
- ATS optimization (production concerns)

**Risk:** scope creep. Phase 3 is 4 weeks in plan, 6-8 realistic. Mitigation: ship
PR-3.1 + 3.2 + 3.4 first as MVP, defer 3.3, 3.5, 3.6, 3.7.

### Phase 4: HITL Apply Agent (Week 11-13 plan, ~3-4 weeks)

**Goal:** Agent fills application forms for jobs with match score >X, user approves
every submit.

**Sub-PRs:**

- PR-4.1: Match scoring (offer ↔ user profile via RAG)
- PR-4.2: Browser automation (Playwright + LLM action decisions)
- PR-4.3: Form-fill orchestration with HITL approval gate
- PR-4.4: State machine for follow-up tracking
- PR-4.5: Replay log + audit trail
- PR-4.6: Safety constraints (rate limit, company blacklist, no-spam)

**Hard constraints (do NOT break):**

- NEVER auto-submit. HITL approval mandatory.
- Rate limit: max N applications/day (configurable)
- Blacklist: companies user explicitly excluded
- Replay log: every agent decision recorded for review

**Senior signals:**

- Agentic workflow design with safety boundaries
- Human-in-the-loop UX patterns
- State machine modeling
- Observability for agent decisions

### Phase 5: Production + MLOps (Week 14-16 plan, ~2-3 weeks)

**Goal:** Deployed system with monitoring, scheduled ingestion, CI/CD.

**Sub-PRs:**

- PR-5.1: Deploy to Railway or Fly.io (cheapest options)
- PR-5.2: Scheduled scraping (cron for HF API + manual reminder UX for HITL portals)
- PR-5.3: Monitoring (Grafana/Sentry — cost tracking, error rates)
- PR-5.4: CI/CD via GitHub Actions
- PR-5.5: Cost dashboard (Anthropic API spend tracking)
- PR-5.6 (optional): Fine-tuned classifier for cost reduction

**Note:** HITL portals (JJIT, NFJ) can't be auto-scheduled — they need user to load
Chrome page. Phase 5 scheduling applies to HF API only + reminders for Polish portals.

## Cross-phase strategic tracks

### Quality track (always-on, parallel to phases)

- PR17 (deferred from PC sprint): salary capture prompt fix
  - Blocked on: manual labeling 30 JJIT+NFJ jobs in `docs/ground_truth/phase1_seed.json`
  - Effort: 1.5h labeling + 3h prompt+re-extract+measure
  - Slot: when N=30+ labeling done, before Phase 3 RAG starts
- Eval framework extensions (PR16 base → LLM-as-judge for resume quality)
- Cost optimization (Phase 5 sub-task)

### Portfolio track (always-on)

- README reframe (Pass 2 deferred from 2026-05-17 strategic sprint)
- `docs/journal.txt` retrospective entries (weekly)
- Blog posts per phase (after Phase 2 done, after Phase 3 done, after Phase 5 done)
- LinkedIn updates aligned with phase milestones
- GitHub Pages dashboard hosting (post-Phase 2)
- Demo video for top of README (post-Phase 4)

### Job application track (parallel to Phase 3+)

- **Start applying after Phase 2 PoC merged** (N=57+ data demo-ready)
- Target: 30-50 applications over Phase 3-5 timeline
- Document interview process per Janvi Kalra style
- Update achievement database based on interview feedback

## Decision rules

**Ship vs polish tension:**

- Phase 1-2: ship fast, polish later (PoC quality is fine)
- Phase 3 RAG: polish more (this is the showcase piece)
- Phase 4 agent: HITL safety > velocity
- Phase 5 production: production-grade required

**Scope creep guardrails:**

- New portal idea? → add to "deferred" list, ship current phase first
- Refactor temptation? → document as ADR, schedule for after current phase
- New framework? → ADR comparing alternatives before adopt

**Quality investigation triggers:**

- Sample peek every ~30 new extracts (catch drift early)
- Re-run eval after every prompt change
- Manual labeling sprint when N=100, N=200, N=500

## What we WON'T do

Explicit anti-goals to prevent scope creep:

- **No LinkedIn portal** in Phase 1-2 (strongest anti-bot, ToS issue)
- **No CrossRef multi-language portals** before Phase 5
- **No general-purpose job aggregator framing** — Polish AI/ML niche only
- **No Streamlit migration** before Phase 5 (HTML dashboard is fine for PoC)
- **No mobile app** ever (out of scope, just bookmark dashboard)
- **No real-time scoring** before Phase 4 (batch is fine)
- **No team collaboration features** (single-user system)
- **No payment integration** (this is personal, not SaaS)

## Timeline forecast

Realistic dates assuming sustained ~15h/week pace:

| Milestone | Target date | Confidence |
|---|---|---|
| Phase 2 PoC merged | 2026-05-18 | done — PR #20 |
| README reframe + roadmap committed | 2026-05-20 | 90% |
| First application sent | 2026-05-22 | 85% |
| PR17 quality fix merged | 2026-05-25 | 80% |
| Phase 3 RAG MVP (PR-3.1+3.2+3.4) | 2026-06-15 | 70% |
| First AI Engineer interview | 2026-06-30 | 65% |
| Phase 3 complete | 2026-07-13 | 60% |
| Phase 4 agent merged | 2026-08-03 | 50% |
| First AI Engineer offer | 2026-08-15 | 45% |

Confidence drops further out — adjust roadmap after every phase merge.

## Update protocol

- Update at every phase merge
- Re-validate forecast dates monthly
- Reorder tracks if priorities shift (e.g., interview offered earlier → rush Phase 3,
  defer Phase 4)
- Commit changes via PR (versioned roadmap = decision audit trail)
