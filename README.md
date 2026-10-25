[![CI](https://github.com/MateuszJastrzebski21/job-market-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/MateuszJastrzebski21/job-market-intelligence/actions/workflows/ci.yml)

# Job Market Intelligence

A personal pipeline for the Polish AI/ML job market. It ingests job postings, extracts structured fields with an LLM, stores them in Postgres with pgvector, evaluates extraction and retrieval quality against hand-labelled sets, and generates market reports and tailored CVs.

```
ingest ──▶ extract ──┬──▶ evaluate  (per-field scores vs labelled set)
                     ├──▶ analyze   (embeddings, clustering, market report)
                     └──▶ retrieve  (RAG over an achievement corpus → tailored CV + cover letter)
```

## Results

**Retrieval (RAG over the achievement corpus).** I built the retrieval layer from scratch and then reimplemented it in LangChain to compare. 15 labelled queries, k = 5:

| System | recall@5 | MRR | nDCG@5 |
|---|---|---|---|
| custom, no rerank | 0.570 | 0.700 | 0.550 |
| custom + cross-encoder rerank | 0.608 | 0.878 | 0.632 |
| LangChain, no rerank | 0.587 | 0.700 | 0.558 |
| LangChain + cross-encoder rerank | 0.608 | 0.906 | 0.642 |

- Custom and LangChain retrieval are statistically indistinguishable. At N = 15, every bootstrap CI on the paired difference crosses zero.
- Reranking is the only change that clearly moves the numbers: about +0.18 MRR.
- Raw runs are in [`experiments/pr32-benchmark/`](experiments/pr32-benchmark/). The write-up is in [ADR-0015](docs/adr/0015-custom-vs-langchain-rag-comparison.md).

**Extraction.** Each LLM extract is scored per field against ground-truth labels: Jaccard similarity for tech-stack lists, recall for salary capture and exact match for seniority. A prompt change is accepted only if it moves these numbers. See [`docs/evaluation_methodology.md`](docs/evaluation_methodology.md) and [ADR-0010](docs/adr/0010-evaluation-framework.md).

## How it works

1. **Ingest.** Every source writes to one `JobPosting` table, so a new source never forks the pipeline.
   - Hugging Face Jobs is pulled from its public API.
   - JustJoinIT and NoFluffJobs prohibit server-side scraping in their terms. They are captured by a Chrome MV3 extension from postings I am already viewing, which posts them to a local FastAPI endpoint ([ADR-0009](docs/adr/0009-hitl-ingestion-pivot.md)).
2. **Extract.** Claude returns seniority, tech stack, salary and remote policy as validated Pydantic models. The extractor:
   - uses prompt caching,
   - tracks tokens per run,
   - treats a refused call as an error rather than an empty record.
3. **Analyze.** sentence-transformer embeddings and KMeans clustering produce a Markdown and single-file HTML market report ([ADR-0011](docs/adr/0011-phase2-poc-choices.md)).
4. **Generate.** Retrieval over a personal achievement corpus produces CV bullets and a cover letter tailored to a posting, at about $0.17 per generation ([ADR-0016](docs/adr/0016-resume-generator-and-research-agent.md)).

Non-trivial decisions are written up as ADRs in [`docs/adr/`](docs/adr/) before the code. 477 pytest tests cover the backend (41 of them start a Postgres test container in Docker) and 89 vitest tests cover the extension. CI runs ruff and strict mypy on pushes to main and on pull requests.

## Quick start

Requires Docker (local Postgres) and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env              # DATABASE_URL, ANTHROPIC_API_KEY, JMI_INGEST_TOKEN
docker compose up -d              # Postgres 15 + pgvector
uv run jmi init-db                # Alembic migrations

uv run jmi scrape --source huggingface --limit 50
uv run jmi extract --limit 50
uv run jmi evaluate               # per-field scores vs labelled set
uv run jmi analyze --output report
uv run jmi serve                  # ingest endpoint for the Chrome extension

uv run jmi ingest-achievements && uv run jmi rag-embed
uv run jmi generate-resume --jd-file path/to/jd.txt --output out/resume.md --budget-usd 0.20
```

`ANTHROPIC_API_KEY` is only needed for extraction and generation. Run `uv run jmi --help` for all commands. The extension in [`extension/`](extension/) is loaded unpacked into Chrome.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1. Ingestion | 3 sources → Postgres → LLM extraction | done |
| 2. Analytics | embeddings, clustering, market report | proof of concept merged |
| 3. RAG CV generator | retrieval, LangChain comparison, CV + cover letter agent | shipped; PDF output and a CV-quality eval pending |
| 4. Apply assistant | match scoring and form filling, human approval on every submission | planned |

The roadmap is in [`docs/roadmap.md`](docs/roadmap.md).

## Stack

Python 3.12, uv, Postgres 15 + pgvector, SQLAlchemy 2.0, Alembic, Anthropic SDK, sentence-transformers, scikit-learn, FastAPI, Typer, Pydantic v2, structlog, Chrome MV3 extension (JavaScript), ruff, mypy strict, pre-commit, GitHub Actions.

## License

[MIT](LICENSE)
