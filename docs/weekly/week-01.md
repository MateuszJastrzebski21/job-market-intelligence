# Week 1 Retro — JMI

## Deliverables (plan vs actual)
- Plan: scraper + LLM extraction + storage, 100+ jobs w bazie
- Actual: HF scraper (9 jobs), Opus 4.7 extractor, 2 ADRs, ground truth seed
- Verdict: ahead on quality, behind on volume (1 portal zamiast 3) — świadomy trade-off

## Co zaskoczyło pozytywnie
- ...

## Co było trudniejsze niż myślałem
- ...

## Co umiem lepiej niż przed Week 1
- ...

## Decyzje które się sprawdziły
- Plan mode przed kodem (złapałem kolejność portali, Opus vs default, cache_control)
- Separated pipeline (ADR-0006) — re-extract bez re-scrape
- Seed file dla Phase 3 eval zamiast hardcoded few-shot

## Czego nie zrobiłem
- build-in-public post (świadomie, decyzja zapadła)
- ADR dla HF scraper decisions (można dopisać post-facto)
- Docker Compose cleanup (niedzielny task)

## Week 2 priority
- CI/GitHub Actions (1h)
- Alembic migrations (foundational przed Week 3 pgvector)
- JJIT scraper (główny task, Playwright + anti-bot)
