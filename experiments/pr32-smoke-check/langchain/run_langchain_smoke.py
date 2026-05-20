"""Run the LangChain RAG pipeline on 5 JD samples and dump smoke-check files.

Operator review material per orchestrator T11. Outputs one
'smoke-{slug}.md' per JD in this directory. Each file contains:

  - Input JD (verbatim)
  - Retrieved chunks (top-5, scored, sectioned)
  - Generated bullets (raw model output)
  - Notes — empty header for the operator to label grounded /
    partial / hallucinated

Hardcoded JD set covers the orchestrator's required 5:
  1. AI Engineer (English)
  2. Junior Backend Java (Polish)
  3. Quant Researcher (English)
  4. ML Engineer (English)
  5. Data Engineer (Polish)

Run from the worktree root:

    cd .claude/worktrees/jmi-pr32-B
    uv run python experiments/pr32-smoke-check/langchain/run_langchain_smoke.py

Idempotent — re-running re-embeds (upsert by deterministic chunk id) and
overwrites the smoke-{slug}.md files. The first run downloads BGE-small
(~130 MB) and BGE-reranker-base (~280 MB). Subsequent runs use the cache.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader — uv run does not source .env automatically, and
    ChatAnthropic (langchain-anthropic) refuses to start without ANTHROPIC_API_KEY
    in os.environ at module-import time. Read the .env at the worktree root and
    inject any KEY=VALUE pairs that are not already set."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.is_file():
        print(f"[warn] no .env at {env_path}")
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        # Use direct assignment when the existing var is empty — shell init
        # may already have set ANTHROPIC_API_KEY="", which setdefault would
        # treat as "already set" and leave broken.
        if not os.environ.get(key):
            os.environ[key] = value


_load_dotenv()

# E402: jmi.* imports must follow _load_dotenv() so ChatAnthropic sees
# ANTHROPIC_API_KEY in os.environ at module-load time.
from jmi.db.base import get_session  # noqa: E402
from jmi.rag_langchain.embedding import get_embeddings  # noqa: E402
from jmi.rag_langchain.ingest import (  # noqa: E402
    ensure_collection_table,
    get_pg_engine,
    get_vector_store,
    ingest_chunks,
)
from jmi.rag_langchain.pipeline import RagPipeline  # noqa: E402
from jmi.rag_langchain.retrieval import ScoredChunk  # noqa: E402
from jmi.storage.achievements import AchievementRepository  # noqa: E402


@dataclass
class SmokeSample:
    slug: str
    title: str
    language: str
    jd: str


SAMPLES: list[SmokeSample] = [
    SmokeSample(
        slug="ai-engineer-english",
        title="AI Engineer (English)",
        language="en",
        jd=(
            "We are hiring an AI Engineer to build LLM-powered features in a Python "
            "codebase. The role owns prompt engineering, retrieval pipelines, and "
            "evaluation infrastructure. You should be comfortable with embeddings, "
            "vector stores (pgvector or similar), retrieval-augmented generation, "
            "and integrating Anthropic/OpenAI APIs end-to-end. Bonus: experience with "
            "agentic workflows, observability for LLM systems (token + cost tracking), "
            "and shipping ML-touching code to production with tests + CI."
        ),
    ),
    SmokeSample(
        slug="junior-backend-java-polish",
        title="Junior Backend Java (Polish)",
        language="pl",
        jd=(
            "Poszukujemy Junior Java Developera do zespołu backendowego. Stack: "
            "Java 17+, Spring Boot, PostgreSQL, Maven/Gradle. Mile widziane: "
            "doświadczenie w pracy z REST API, testami jednostkowymi (JUnit, "
            "Mockito), wielowątkowością, oraz utrzymaniem aplikacji produkcyjnych. "
            "Cenimy umiejętność czytania cudzego kodu, dokumentowanie decyzji oraz "
            "współpracę w code review. Bonus: doświadczenie z systemami legacy "
            "i samodzielne projekty pokazujące inicjatywę."
        ),
    ),
    SmokeSample(
        slug="quant-researcher-english",
        title="Quant Researcher (English)",
        language="en",
        jd=(
            "Quantitative Researcher position on the systematic equities desk. "
            "You will own end-to-end research from data ingestion through model "
            "calibration to backtest. Strong Python (pandas, numpy, scipy), "
            "comfort with options pricing (Black-Scholes, implied vol surfaces), "
            "Monte Carlo methods, and risk-neutral pricing. We value clean "
            "experimentation, careful statistical reasoning, and the ability to "
            "communicate findings to PMs. PhD nice-to-have, not required."
        ),
    ),
    SmokeSample(
        slug="ml-engineer-english",
        title="ML Engineer (English)",
        language="en",
        jd=(
            "ML Engineer to productionize models from research notebooks into "
            "shipped features. Stack: Python, PyTorch, scikit-learn, MLflow, "
            "Postgres, Docker. You should be comfortable with feature engineering, "
            "cross-validation, hyperparameter search, and serving models behind a "
            "REST API. Bonus: experience with text data, embeddings, or "
            "competition-grade tabular modelling. We value engineering rigor over "
            "raw research output — measurable improvements with reproducible "
            "experiments."
        ),
    ),
    SmokeSample(
        slug="data-engineer-polish",
        title="Data Engineer (Polish)",
        language="pl",
        jd=(
            "Data Engineer — projektowanie i utrzymanie pipeline'ów danych w "
            "środowisku produkcyjnym. Stack: Python, SQL (PostgreSQL), Airflow lub "
            "podobny orchestrator, batch processing (Spark/Pandas), Docker. "
            "Oczekujemy doświadczenia w pracy z dużymi wolumenami danych, "
            "monitoringu jakości danych oraz w pisaniu czystego kodu z testami. "
            "Mile widziane: praca z systemami wielowątkowymi, doświadczenie z "
            "obciążeniem produkcyjnym oraz znajomość praktyk dobrego inżynierowania."
        ),
    ),
]


def _ensure_corpus(store: object) -> int:
    """Read achievements from the DB and (re-)embed them into the LC collection."""
    with get_session() as session:
        repo = AchievementRepository(session)
        achievements = repo.list_all(limit=200)
    print(f"[corpus] {len(achievements)} achievements in dev DB")
    chunk_count = ingest_chunks(store, achievements)  # type: ignore[arg-type]
    print(f"[corpus] embedded {chunk_count} chunks into langchain_achievement_embeddings")
    return chunk_count


def _format_chunk(idx: int, chunk: ScoredChunk) -> str:
    return (
        f"### {idx}. score={chunk.score:.3f}  section={chunk.section}  "
        f"chunk_id={chunk.chunk_id}\n\n"
        f"achievement_id: `{chunk.achievement_id}`  chunk_index: {chunk.chunk_index}\n\n"
        "```\n"
        f"{chunk.chunk_text}\n"
        "```\n"
    )


def _render_smoke(sample: SmokeSample, chunks: list[ScoredChunk], bullets: str) -> str:
    chunk_block = "\n".join(_format_chunk(i + 1, c) for i, c in enumerate(chunks))
    return f"""# Smoke check (LangChain): {sample.title}

**Pipeline:** `jmi.rag_langchain.pipeline.RagPipeline` (PR-3.2 Worktree B)
**Language:** {sample.language}
**K:** 5
**Rerank:** on (CrossEncoderReranker with bge-reranker-base)

## Input JD

```
{sample.jd}
```

## Retrieved Chunks (top-5)

{chunk_block}

## Generated Bullets

{bullets}

## Notes

_Operator labels:_ grounded / partial / hallucinated

- bullet 1:
- bullet 2:
- bullet 3:
- bullet 4:
- bullet 5:

_Side-by-side comparison with Worktree A's `experiments/pr32-smoke-check/{sample.slug}.md`:_
"""


def main() -> int:
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[setup] building PGEngine")
    engine = get_pg_engine()
    print("[setup] ensuring collection table")
    ensure_collection_table(engine)
    print("[setup] loading BGE-small embedder (may download)")
    embeddings = get_embeddings()
    store = get_vector_store(engine, embeddings)

    _ensure_corpus(store)

    pipeline = RagPipeline(store=store)

    for sample in SAMPLES:
        print(f"\n[smoke] {sample.slug}: retrieving top-5 w/ rerank")
        try:
            chunks = pipeline.retrieve_top_k(sample.jd, k=5, rerank=True)
            print(f"[smoke] {sample.slug}: generating bullets")
            bullets = pipeline.generate_bullets(sample.jd, k=5, rerank=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[smoke] {sample.slug}: FAILED — {type(exc).__name__}: {exc}")
            (out_dir / f"smoke-{sample.slug}.md").write_text(
                f"# Smoke check (LangChain): {sample.title}\n\n"
                f"**FAILED** — {type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
            continue
        out_path = out_dir / f"smoke-{sample.slug}.md"
        out_path.write_text(_render_smoke(sample, chunks, bullets), encoding="utf-8")
        print(f"[smoke] {sample.slug}: wrote {out_path.relative_to(Path.cwd())}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
