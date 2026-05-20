# Benchmark — `langchain-norerank`

- **k:** 5
- **n_queries:** 15
- **seed_version:** 1
- **seed_file:** `/Users/mateusz/Desktop/job-market-intelligence/.claude/worktrees/jmi-pr32-C/docs/ground_truth/rag_retrieval_seed.json`
- **timestamp:** 2026-05-20T16:08:49.371707+00:00
- **config:** `pipeline`=`langchain`, `rerank`=`False`

## Aggregate (mean; CIs computed offline via jmi.evaluation.bootstrap_ci)

| Metric | Value |
| --- | --- |
| recall@5 | 0.000 |
| MRR | 0.000 |
| nDCG@5 | 0.000 |

## Per-query breakdown

| query_id | lang | recall@5 | MRR | nDCG@5 | top-5 retrieved |
| --- | --- | --- | --- | --- | --- |
| `single-java-backend` | en | 0.000 | 0.000 | 0.000 | — |
| `single-quant-options` | en | 0.000 | 0.000 | 0.000 | — |
| `single-llm-agent` | en | 0.000 | 0.000 | 0.000 | — |
| `single-ml-competition` | en | 0.000 | 0.000 | 0.000 | — |
| `single-fullstack-fastapi` | en | 0.000 | 0.000 | 0.000 | — |
| `cross-python-ml-pytorch` | en | 0.000 | 0.000 | 0.000 | — |
| `cross-rest-api-design` | en | 0.000 | 0.000 | 0.000 | — |
| `cross-data-engineering-postgres` | en | 0.000 | 0.000 | 0.000 | — |
| `cross-quant-finance` | en | 0.000 | 0.000 | 0.000 | — |
| `cross-junior-java-oop` | en | 0.000 | 0.000 | 0.000 | — |
| `pl-java-spring-backend` | pl | 0.000 | 0.000 | 0.000 | — |
| `pl-ml-pytorch` | pl | 0.000 | 0.000 | 0.000 | — |
| `pl-junior-backend-python` | pl | 0.000 | 0.000 | 0.000 | — |
| `edge-vague-fast-learner` | en | 0.000 | 0.000 | 0.000 | — |
| `edge-ambiguous-trading-bot` | en | 0.000 | 0.000 | 0.000 | — |

---

**Note on CIs:** this script computes means only. Bootstrap CIs are
computed offline by feeding the per-query vectors into
`jmi.evaluation.retrieval_metrics.bootstrap_ci` (or, for paired
comparison, `paired_bootstrap_ci`). See ADR-0015 §benchmark.
