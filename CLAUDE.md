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
- FastAPI added in Phase 2 (Week 5+) when dashboard needs endpoints
- Sync first, async only when measured bottleneck


## Phase 1 portal order (decided Week 1)

1. HuggingFace Jobs — Week 1 (easiest technically, API-friendly, AI-specific)
2. JustJoinIT — Week 2 (main target for job hunt, SPA + anti-bot)
3. NoFluffJobs — Week 3 (Polish market coverage, dedup test vs JJIT)
4. Wellfound OR YC Work at a Startup — Week 4 (one of them, pick based on 
   junior-friendly volume analysis done in Week 3)

LinkedIn: OFF the table (ToS + anti-bot, not worth).
Otta: OFF the table (EU scale-ups, junior roles rare).

Rationale: Week 1 prioritizes technical safety (HF Jobs is safe first scraper 
to learn the framework). Week 2 switches to JJIT which is the actual job hunt 
target portal despite being harder technically - by then BaseScraper + 
repository + extractor are done, only scraping SPA is the new problem.