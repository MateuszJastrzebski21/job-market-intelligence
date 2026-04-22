# job-market-intelligence

Scrape, extract, and analyze job postings. Phase 1 targets Wellfound; later
phases add more sources, embeddings, and a dashboard.

## Stack

- Python 3.12, managed by [uv](https://docs.astral.sh/uv/)
- Postgres 15 + pgvector (single DB for data + embeddings)
- Typer CLI, Pydantic v2, SQLAlchemy 2.0, structlog

## Quickstart

```bash
# 1. Install deps + create virtualenv
uv sync

# 2. Copy env and start Postgres
cp .env.example .env
docker compose up -d

# 3. Create tables
uv run jmi init-db

# 4. See available commands
uv run jmi --help

# 5. Run tests
uv run pytest
```

## Layout

```
src/jmi/
  cli.py          # Typer entry point (jmi ...)
  config.py       # pydantic-settings Settings
  logging.py      # structlog setup
  models/         # Pydantic domain/DTO models
  db/             # SQLAlchemy ORM + session factory
  storage/        # Repository pattern (Pydantic <-> ORM boundary)
  sources/        # Scrapers (wellfound next)
  extractors/     # LLM extractors (weekend)
tests/
docker/init.sql   # CREATE EXTENSION vector (Alembic lands Week 2)
```
