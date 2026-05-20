"""Generate the five PR-3.2 smoke-check files (Worktree A, T11).

Run from the repo root:

    uv run python experiments/pr32-smoke-check/custom/run.py

Reads the 11 achievements / 44 chunks already embedded in the dev DB, runs
the custom RAG pipeline + Claude bullet generator for each of the five
sample job descriptions, and writes one ``smoke-{slug}.md`` per JD into
this directory.

Outputs are *local files* — H1/S-2 forbids logging chunk text, but the
smoke-check report is an audit artifact the operator owns; it intentionally
records full retrieved chunks for inspection. The experiment directory is
gitignored so the artifacts do not land in the repo.
"""

from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from jmi.db.base import get_session
from jmi.rag.embedding import CustomEmbedder
from jmi.rag.generation import Generator
from jmi.rag.pipeline import RagPipeline
from jmi.rag.reranking import CustomReranker
from jmi.rag.retrieval import CustomRetriever, ScoredChunk


@dataclass(frozen=True)
class _Jd:
    slug: str
    role: str
    language: str
    text: str


_JDS: list[_Jd] = [
    _Jd(
        slug="ai-engineer-en",
        role="AI Engineer (English)",
        language="en",
        text=textwrap.dedent(
            """\
            We are looking for an AI Engineer to ship production LLM features.
            You will design retrieval-augmented generation pipelines over private
            corpora, evaluate retrieval quality with recall and nDCG metrics,
            wire models to Postgres with pgvector, and own the prompt engineering
            for downstream generation. Strong Python required. Bonus: experience
            with sentence-transformers, embedding-store schema design, and
            building evaluation harnesses for retrieval and generation.
            """
        ),
    ),
    _Jd(
        slug="junior-java-pl",
        role="Junior Backend Java Developer (Polish)",
        language="pl",
        text=textwrap.dedent(
            """\
            Poszukujemy juniora Java do zespołu backendowego pracującego nad
            systemem dla administracji publicznej. Wymagania: znajomość Javy
            (Spring/Hibernate plus), pisanie testów, praca z bazami danych
            (PostgreSQL, MySQL), wielowątkowość, REST API. Mile widziane:
            doświadczenie z systemami logistycznymi lub transportowymi,
            algorytmy grafowe, projekty open source. Pracujemy hybrydowo
            w Warszawie.
            """
        ),
    ),
    _Jd(
        slug="quant-researcher-en",
        role="Quant Researcher (English)",
        language="en",
        text=textwrap.dedent(
            """\
            Quantitative researcher to develop systematic trading strategies on
            equity options and futures. Responsibilities include modelling
            implied volatility surfaces, backtesting strategies with realistic
            transaction-cost models, and prototyping in Python (NumPy, pandas).
            Strong background in mathematical statistics and options pricing
            (Black-Scholes, vol surfaces, Greeks). Competition placements in
            quant or algorithmic-trading contests are a plus.
            """
        ),
    ),
    _Jd(
        slug="ml-engineer-en",
        role="ML Engineer (English)",
        language="en",
        text=textwrap.dedent(
            """\
            ML Engineer to own training and serving of forecasting models in
            production. Day-to-day: build feature pipelines, train neural
            networks (PyTorch / scikit-learn), evaluate against held-out splits
            with the right metric for the problem (regression, classification,
            ranking), and ship the model behind a low-latency inference API.
            Experience reading and re-implementing methods from research papers
            is a strong plus.
            """
        ),
    ),
    _Jd(
        slug="data-engineer-pl",
        role="Data Engineer (Polish)",
        language="pl",
        text=textwrap.dedent(
            """\
            Inżynier danych do budowy pipeline'ów ETL/ELT i monitorowania
            jakości danych. Wymagamy bardzo dobrej znajomości Pythona i SQL,
            doświadczenia z PostgreSQL, projektowania schematów baz danych,
            pracy z dużymi zbiorami danych oraz konteneryzacji (Docker).
            Doświadczenie z LLM / embeddingami i bazami wektorowymi (pgvector)
            mile widziane. Praca nad realnym produktem analitycznym.
            """
        ),
    ),
]


def _render_chunks(chunks: list[ScoredChunk]) -> str:
    out: list[str] = []
    for i, c in enumerate(chunks, start=1):
        out.append(f"### Chunk {i} — score {c.score:.4f}")
        out.append("")
        out.append(f"- `chunk_id`: `{c.chunk_id}`")
        out.append(f"- `achievement_id`: `{c.achievement_id}`")
        out.append(f"- `chunk_index`: {c.chunk_index}")
        out.append("")
        out.append("```text")
        out.append(c.chunk_text)
        out.append("```")
        out.append("")
    return "\n".join(out)


def _render_file(jd: _Jd, chunks: list[ScoredChunk], bullets: str, model: str) -> str:
    # Flush-left template — interpolated sub-renders carry no leading
    # whitespace, so a ``textwrap.dedent`` pass over the outer template would
    # mis-strip any line whose only common prefix is in the indented sections
    # (Python doc-string subtlety). Writing the template flush-left is the
    # simplest fix.
    return (
        f"# Smoke check — {jd.role}\n\n"
        f"- **JD slug:** `{jd.slug}`\n"
        f"- **Language:** `{jd.language}`\n"
        "- **Pipeline:** custom RAG with reranker (`bge-small-en-v1.5` + "
        "`bge-reranker-base`), top-K = 5\n"
        f"- **Generator model:** `{model}`\n\n"
        "## Input JD\n\n"
        "```text\n"
        f"{jd.text.strip()}\n"
        "```\n\n"
        "## Retrieved Chunks (top-5 after rerank)\n\n"
        f"{_render_chunks(chunks)}\n"
        "## Generated Bullets\n\n"
        "```markdown\n"
        f"{bullets.strip()}\n"
        "```\n\n"
        "## Notes (operator labels)\n\n"
        "- Bullet 1 — [grounded / partial / hallucinated]:\n"
        "- Bullet 2 — [grounded / partial / hallucinated]:\n"
        "- Bullet 3 — [grounded / partial / hallucinated]:\n"
        "- Bullet 4 — [grounded / partial / hallucinated]:\n"
        "- Bullet 5 — [grounded / partial / hallucinated]:\n"
    )


def main() -> int:
    out_dir = Path(__file__).parent
    pipeline = RagPipeline(CustomRetriever(CustomEmbedder()), CustomReranker())
    generator = Generator()

    failures = 0
    for jd in _JDS:
        print(f"=== {jd.slug} ===", flush=True)
        try:
            with get_session() as session:
                chunks = pipeline.retrieve_top_k(session, jd.text, k=5)
        except Exception as exc:
            print(f"  retrieve failed: {exc!r}", flush=True)
            failures += 1
            continue
        try:
            result = generator.generate_bullets(jd.text, chunks)
        except Exception as exc:
            print(f"  generate failed: {exc!r}", flush=True)
            failures += 1
            continue
        doc = _render_file(jd, chunks, result.bullets_markdown, result.model)
        target = out_dir / f"smoke-{jd.slug}.md"
        target.write_text(doc, encoding="utf-8")
        print(
            f"  wrote {target.name}  (in={result.input_tokens} out={result.output_tokens} tokens)",
            flush=True,
        )

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
