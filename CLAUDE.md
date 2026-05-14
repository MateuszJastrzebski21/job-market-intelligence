Przeczytaj CLAUDE.md w root repo.

Kontekst: Week 1 of Phase 1. Projekt jest świeży, repo pusty 
poza CLAUDE.md i README szkieletem.

Zadanie Week 1: skonfigurować projekt i zaimplementować 
end-to-end pipeline dla Wellfound (scrape -> LLM extract -> Postgres).

Podziel to na kroki. Zacznij od Plan Mode: 
pokaż mi konkretny plan implementacji Week 1 w rozbiciu na 
dzisiejszą sesję (1-2h). Nie pisz jeszcze kodu. 

W planie uwzględnij:
1. uv init + pyproject.toml z depami (wypisz które)
2. Struktura folderów (src/jmi/...)
3. docker-compose.yml dla Postgres + pgvector
4. Pydantic models dla JobPosting i JobExtract
5. Storage layer z repository pattern
6. structlog configuration
7. Pierwszy pytest setup
8. .env.example i .gitignore

W każdym kroku powiedz mi DLACZEGO tak a nie inaczej 
(alternative + krótki trade-off).

Nie dotykaj scrapera ani LLM extractora w tej sesji — 
to zostawiamy na weekend.

Koniec sesji dzisiejszej: `docker compose up` działa, 
`uv run pytest` przechodzi (nawet z jednym testem), 
`uv run jmi --help` pokazuje CLI scaffold.

- Python 3.12, uv for package management
- Postgres 15 + pgvector (single DB for data + embeddings)
- Docker Compose for local Postgres
- Typer for CLI (Phase 1-2)
- FastAPI: Phase 1 since Week 2 for the ingest endpoint (ADR-0009); dashboard endpoints still in Phase 2
- Sync first, async only when measured bottleneck


## Phase 1 portal order (updated Week 2 — see ADR-0008)

1. HuggingFace Jobs — Week 1 (easiest technically, API-friendly, AI-specific) — DONE
2. NoFluffJobs — Week 2 (Polish market coverage; promoted from Week 3 after 
   JJIT pivot)
3. Wellfound OR YC Work at a Startup — Week 3 (one of them, pick based on 
   junior-friendly volume analysis done in Week 2 retro)
4. The other of Wellfound / YC, or Bulldogjob — Week 4

JustJoinIT: OFF the table (regulamin 11.3 prohibits automated extraction; 
robots.txt Disallow /api/; see docs/adr/0008-jjit-removed-from-phase-1.md).
LinkedIn: OFF the table (ToS + anti-bot, not worth).
Otta: OFF the table (EU scale-ups, junior roles rare).

Rationale: Week 1 prioritized technical safety (HF Jobs as a low-risk first 
scraper to learn the framework). Week 2 was originally JJIT (the actual job 
hunt target despite the SPA + anti-bot challenge), but ToS diligence in the 
Week 2 plan-mode session surfaced an explicit prohibition on automated data 
extraction in regulamin 11.3, backed by the 2001 Polish Database Protection 
Act. NFJ — already on the roadmap for Week 3 — moves up to fill the slot. 
The architectural patterns researched for JJIT (Alembic migration, separated 
3-step pipeline, multi-company mapper, Quill-aware HTML parser) port to NFJ; 
see docs/_archived/jjit-plan-abandoned.md.