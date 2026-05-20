#!/usr/bin/env python3
"""Standalone PR-3.2 benchmark runner — invoke from worktree A or B.

Why a script and not the CLI: Worktree C's `jmi rag-benchmark` lives in C's
package tree, but worktree A's `jmi.rag.*` and worktree B's `jmi.rag_langchain.*`
live in separate worktrees with separate `jmi` packages. Python's regular-
package semantics mean once `jmi` is resolved to one worktree's `src/`, the
other's `src/` is invisible. This script avoids the collision by:

- Re-implementing the small metric set (recall@k, MRR, nDCG@k, mean) inline,
  so no `jmi.evaluation.*` import is needed.
- Reading C's seed JSON as a plain file via `pathlib`.
- Importing the RagPipeline of whichever worktree it is run from — A or B.

Usage::

    cd .claude/worktrees/jmi-pr32-A   # or jmi-pr32-B
    uv run python \\
      ../jmi-pr32-C/experiments/pr32-benchmark/run_from_worktree.py \\
      --pipeline custom --rerank \\
      --seed ../jmi-pr32-C/docs/ground_truth/rag_retrieval_seed.json \\
      --out ../jmi-pr32-C/experiments/pr32-benchmark/custom-rerank.md

The script writes a markdown report shaped like
`format_benchmark_markdown` in `jmi.evaluation.benchmark` so the artefacts
look the same as if the canonical harness had run.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

# ---------- minimal metrics (mirrors jmi.evaluation.retrieval_metrics) ----------


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    top_k = set(ranked_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def mrr(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    if not relevant_ids:
        return 0.0
    for position, cid in enumerate(ranked_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    # Binary relevance; DCG = sum(rel_i / log2(i+1)) for top-k
    dcg = 0.0
    for position, cid in enumerate(ranked_ids[:k], start=1):
        rel = 1.0 if cid in relevant_ids else 0.0
        dcg += rel / math.log2(position + 1)
    # Ideal: as many 1s as possible at the top.
    ideal_count = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(p + 1) for p in range(1, ideal_count + 1))
    return dcg / idcg if idcg > 0 else 1.0


SECTION_ORDER = ("context", "approach", "impact", "lessons")


# ---------- chunk-id resolver ----------


def build_resolver(session: Any) -> Any:
    """Map (achievement_id, chunk_index) -> canonical `{stem}::{section}`."""
    from sqlalchemy import select

    from jmi.db.models import AchievementORM

    rows = session.execute(select(AchievementORM.id, AchievementORM.source_path)).all()
    by_id = {row[0]: row[1] for row in rows}

    def resolver(achievement_id: Any, chunk_index: int) -> str:
        # Worktree A returns UUID; worktree B stores the achievement_id as a
        # string in LangChain metadata. Coerce so both look the same to the
        # by_id dict.
        if not isinstance(achievement_id, UUID):
            achievement_id = UUID(str(achievement_id))
        source_path = by_id[achievement_id]
        stem = Path(source_path).stem
        section = SECTION_ORDER[chunk_index]
        return f"{stem}::{section}"

    return resolver


# ---------- pipeline runners ----------


def run_custom(query: str, k: int, rerank: bool, session: Any, resolver: Any) -> list[str]:
    """Worktree A's RagPipeline. Constructs the pipeline on first call (cached)."""
    if not hasattr(run_custom, "_pipeline"):
        from jmi.rag.embedding import CustomEmbedder
        from jmi.rag.pipeline import RagPipeline
        from jmi.rag.reranking import CustomReranker
        from jmi.rag.retrieval import CustomRetriever

        embedder = CustomEmbedder()
        retriever = CustomRetriever(embedder)
        reranker = CustomReranker() if rerank else None
        run_custom._pipeline = RagPipeline(retriever, reranker=reranker)  # type: ignore[attr-defined]
    pipe = run_custom._pipeline  # type: ignore[attr-defined]
    chunks = pipe.retrieve_top_k(session, query, k=k)
    return [resolver(c.achievement_id, c.chunk_index) for c in chunks]


def run_langchain(query: str, k: int, rerank: bool, session: Any, resolver: Any) -> list[str]:
    """Worktree B's RagPipeline. Constructs the pipeline on first call (cached)."""
    if not hasattr(run_langchain, "_pipeline"):
        from jmi.rag_langchain.pipeline import RagPipeline

        run_langchain._pipeline = RagPipeline()  # type: ignore[attr-defined]
    pipe = run_langchain._pipeline  # type: ignore[attr-defined]
    chunks = pipe.retrieve_top_k(query, k=k, rerank=rerank)
    # B's ScoredChunk has the same achievement_id / chunk_index shape; mapping
    # to canonical id may need a different path if metadata differs. We rely on
    # the worktree B contract that `c.achievement_id` and `c.chunk_index` exist.
    return [resolver(c.achievement_id, c.chunk_index) for c in chunks]


# ---------- main ----------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", required=True, choices=("custom", "langchain"))
    parser.add_argument("--rerank", dest="rerank", action="store_true", default=True)
    parser.add_argument("--no-rerank", dest="rerank", action="store_false")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("docs/ground_truth/rag_retrieval_seed.json"),
        help="Path to C's rag_retrieval_seed.json (relative to wherever you cd'd to).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Where to write the markdown report (typically a path under C).",
    )
    args = parser.parse_args(argv)

    # ---- Load seed ----
    if not args.seed.exists():
        print(f"seed file not found: {args.seed}", file=sys.stderr)
        return 2
    seed_data = json.loads(args.seed.read_text(encoding="utf-8"))
    entries = seed_data["entries"]
    seed_version = seed_data.get("version", "?")

    # ---- DB session ----
    from jmi.db.base import get_session

    runner = run_custom if args.pipeline == "custom" else run_langchain

    config = {"rerank": args.rerank, "pipeline": args.pipeline}
    name = f"{args.pipeline}-{'rerank' if args.rerank else 'norerank'}"
    timestamp = datetime.now(UTC).isoformat()

    per_query: list[dict[str, Any]] = []
    with get_session() as session:
        resolver = build_resolver(session)
        for entry in entries:
            query = entry["query"]
            relevant = set(entry["relevant_chunk_ids"])
            try:
                retrieved = runner(query, args.k, args.rerank, session, resolver)
            except Exception as exc:  # noqa: BLE001
                print(f"query {entry['id']} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                retrieved = []
            r_at_k = recall_at_k(retrieved, relevant, args.k)
            mrr_val = mrr(retrieved, relevant)
            n_at_k = ndcg_at_k(retrieved, relevant, args.k)
            per_query.append(
                {
                    "query_id": entry["id"],
                    "query_language": entry.get("query_language", "en"),
                    "relevant": list(entry["relevant_chunk_ids"]),
                    "retrieved": retrieved,
                    "recall": r_at_k,
                    "mrr": mrr_val,
                    "ndcg": n_at_k,
                }
            )
            print(
                f"  {entry['id']:30s}  r@{args.k}={r_at_k:.3f}  mrr={mrr_val:.3f}  "
                f"ndcg={n_at_k:.3f}",
                file=sys.stderr,
            )

    # ---- Aggregate ----
    if per_query:
        mean_recall = sum(q["recall"] for q in per_query) / len(per_query)
        mean_mrr = sum(q["mrr"] for q in per_query) / len(per_query)
        mean_ndcg = sum(q["ndcg"] for q in per_query) / len(per_query)
    else:
        mean_recall = mean_mrr = mean_ndcg = 0.0

    # ---- Render markdown ----
    lines: list[str] = []
    lines.append(f"# Benchmark — `{name}`")
    lines.append("")
    lines.append(f"- **k:** {args.k}")
    lines.append(f"- **n_queries:** {len(per_query)}")
    lines.append(f"- **seed_version:** {seed_version}")
    lines.append(f"- **seed_file:** `{args.seed}`")
    lines.append(f"- **timestamp:** {timestamp}")
    cfg = ", ".join(f"`{k}`=`{v}`" for k, v in sorted(config.items()))
    lines.append(f"- **config:** {cfg}")
    lines.append("")
    lines.append("## Aggregate (mean; CIs computed offline via jmi.evaluation.bootstrap_ci)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| recall@{args.k} | {mean_recall:.3f} |")
    lines.append(f"| MRR | {mean_mrr:.3f} |")
    lines.append(f"| nDCG@{args.k} | {mean_ndcg:.3f} |")
    lines.append("")
    lines.append("## Per-query breakdown")
    lines.append("")
    lines.append(
        f"| query_id | lang | recall@{args.k} | MRR | nDCG@{args.k} | top-{args.k} retrieved |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for q in per_query:
        retrieved_short = ", ".join(f"`{cid}`" for cid in q["retrieved"]) or "—"
        lines.append(
            f"| `{q['query_id']}` | {q['query_language']} | "
            f"{q['recall']:.3f} | {q['mrr']:.3f} | {q['ndcg']:.3f} | "
            f"{retrieved_short} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Note on CIs:** this script computes means only. Bootstrap CIs are")
    lines.append("computed offline by feeding the per-query vectors into")
    lines.append("`jmi.evaluation.retrieval_metrics.bootstrap_ci` (or, for paired")
    lines.append("comparison, `paired_bootstrap_ci`). See ADR-0015 §benchmark.")
    lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}", file=sys.stderr)

    # ---- Also dump a JSON sidecar for paired-bootstrap recomputation ----
    sidecar = args.out.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "name": name,
                "config": config,
                "k": args.k,
                "seed_version": seed_version,
                "seed_file": str(args.seed),
                "timestamp": timestamp,
                "per_query": per_query,
                "aggregate": {
                    "recall": mean_recall,
                    "mrr": mean_mrr,
                    "ndcg": mean_ndcg,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {sidecar}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
