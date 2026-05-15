# Next session — NoFluffJobs scraper plan mode

## Status
- ADR-0008 merged: JJIT out of Phase 1
- NFJ promoted to Week 2 (was Week 3)
- HF scraper + Opus extractor stable
- Week 1 retro committed (partial)

## Plan jutro (lub następna sesja)

### Step 1 - DevTools research na NFJ (ja, 15 min)
1. Otwórz https://nofluffjobs.com
2. F12 → Network tab → filter "offers" albo "postings" 
3. Reload, znajdź XHR/Fetch który ma response z listą ofert (kilkadziesiąt kB, nie tracker)
4. Copy as cURL → wklej do rozmowy z Claude Desktop
5. **ZANIM** Claude Code: sprawdź NFJ robots.txt i ToS!
   - https://nofluffjobs.com/robots.txt
   - Footer NFJ → szukaj "Regulamin" / "Terms"
   - Search po: scrap*, automatyzacj*, bot, robot, API, pobieranie
   - Jeśli zabronione → szukamy następnego (Wellfound? YC?)

### Step 2 - Plan mode z Claude Code (po pozytywnym ToS check)
Prompt podobny do JJIT plan-mode ale z NFJ data + reuse architectural decisions z archived JJIT plan:
- Alembic-first PR
- Separated 3-step pipeline (scrape → fetch-details → extract) jeśli NFJ ma split endpoint  
- Multi-company refactor (już zaplanowany)
- HTML parser (już zaprojektowany)
- Structured data Option A (raw_payload only)

## Decyzje już podjęte
- Portal order: HF ✓ → NFJ (next) → Wellfound/YC → ...
- LinkedIn out
- JJIT out (ADR-0008)
- Otta out
- Auto-apply human-in-the-loop, nie auto-submit
- Custom RAG od zera, potem LangChain comparison

## Heads up
- ToS check **przed** kodem, nie po. JJIT lesson learned.
- 80% planu JJIT reuse w NFJ — patrz docs/_archived/jjit-plan-abandoned.md
- BaseScraper dopiero po 3 konkretach (rule of three)
- Cloud environment skonfiguruj **wieczorem na implementację** (nie dzień planowania)
## Quality investigation findings (2026-05-15 morning)

### Sample peek: 10 fresh JJIT extracts via Claude Opus 4.7

| Title | desc_len | seniority | tech_count | salary |
|---|---|---|---|---|
| AI Architect | 2460 | senior | 5 items | NULL |
| Senior AI Software Engineer | 3942 | senior | 14 items | NULL |
| Senior Programista Agentic AI | 1944 | senior | 12 items | NULL |
| Copilot & Agent Engineer | 6519 | senior | 10 items | NULL |
| Senior AI Engineer | 6132 | senior | 15 items | NULL |
| Project Manager (AI) | 5798 | mid | 1 (Jira) | NULL |
| Delivery Product Manager | 3447 | mid | 1 (SQL) | PLN |
| AI Engineer (middle) | 2096 | mid | 6 items | NULL |
| GenAI Architect | 2459 | senior | 5 items | NULL |
| Senior AI/ML Engineer MLOps | 4126 | senior | 18 items | NULL |

### Recalibrated quality breakdown

- tech_stack: 8/10 (scales with description length, 10-15 items for detailed jobs)
- seniority: 8/10 (mid/senior split sensible)
- remote_policy: 9/10 (capture good)
- salary: 2/10 - **CRITICAL BUG** (salary in description but not extracted)
- coverage: 5/10 (N=37, AI/ML niche only)

### Salary bug � confirmed scenario (a)

RITS "AI Engineer (middle)" description contains explicitly:
"Stawka: do 145 PLN/h"

But extract returned salary_min/max/currency = NULL.

Diagnosis: Few-shot examples in phase1_seed.json have all salary=null
(3 HF jobs without ranges). Claude learns "salary often null, default to null
when uncertain". Polish "Stawka: do 145 PLN/h" format also non-standard
vs typical "X-Y PLN/month" pattern.

### Action: 3-PR sequence

PR16: Eval framework + baseline measurement (this PR)
PR17: Prompt improvements + better few-shot examples
PR18: Re-extract with improved prompt + measure improvement

Portfolio story: "8.5x salary recall improvement via systematic engineering."
