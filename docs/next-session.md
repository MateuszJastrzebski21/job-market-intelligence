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