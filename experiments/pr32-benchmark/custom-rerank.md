# Benchmark — `custom-rerank`

- **k:** 5
- **n_queries:** 15
- **seed_version:** 1
- **seed_file:** `/Users/mateusz/Desktop/job-market-intelligence/.claude/worktrees/jmi-pr32-C/docs/ground_truth/rag_retrieval_seed.json`
- **timestamp:** 2026-05-20T16:06:24.016028+00:00
- **config:** `pipeline`=`custom`, `rerank`=`True`

## Aggregate (mean; CIs computed offline via jmi.evaluation.bootstrap_ci)

| Metric | Value |
| --- | --- |
| recall@5 | 0.608 |
| MRR | 0.878 |
| nDCG@5 | 0.632 |

## Per-query breakdown

| query_id | lang | recall@5 | MRR | nDCG@5 | top-5 retrieved |
| --- | --- | --- | --- | --- | --- |
| `single-java-backend` | en | 1.000 | 1.000 | 0.947 | `red-ocean-junior-java-developer::context`, `red-ocean-junior-java-developer::approach`, `red-ocean-junior-java-developer::lessons`, `hackyeah-2025-transport-tracker::approach`, `red-ocean-junior-java-developer::impact` |
| `single-quant-options` | en | 1.000 | 1.000 | 0.967 | `volatility-surface-coding-jesus-feature::approach`, `volatility-surface-coding-jesus-feature::context`, `volatility-surface-coding-jesus-feature::lessons`, `volatility-surface-coding-jesus-feature::impact`, `quantfolio-javafx-portfolio-simulator::approach` |
| `single-llm-agent` | en | 1.000 | 1.000 | 0.906 | `imc-prosperity-4-agentic-autoresearch::approach`, `imc-prosperity-4-agentic-autoresearch::lessons`, `imc-prosperity-4-agentic-autoresearch::impact`, `imc-prosperity-4-agentic-autoresearch::context`, `jmi-flagship-project::approach` |
| `single-ml-competition` | en | 0.333 | 1.000 | 0.469 | `car-price-prediction-dsc-pjatk::approach`, `engineering-thesis-btc-signal-prediction::approach`, `car-price-prediction-dsc-pjatk::lessons`, `imc-prosperity-4-agentic-autoresearch::approach`, `engineering-thesis-btc-signal-prediction::impact` |
| `single-fullstack-fastapi` | en | 0.667 | 1.000 | 0.765 | `hackyeah-2025-transport-tracker::approach`, `hackyeah-2025-transport-tracker::impact`, `jmi-flagship-project::approach`, `red-ocean-junior-java-developer::context`, `imc-prosperity-4-agentic-autoresearch::approach` |
| `cross-python-ml-pytorch` | en | 0.400 | 1.000 | 0.553 | `bus-punctuality-neural-network::approach`, `bus-punctuality-neural-network::impact`, `jmi-flagship-project::impact`, `bus-punctuality-neural-network::lessons`, `pjatk-data-science-club-membership::approach` |
| `cross-rest-api-design` | en | 0.750 | 1.000 | 0.832 | `hackyeah-2025-transport-tracker::approach`, `red-ocean-junior-java-developer::approach`, `jmi-flagship-project::approach`, `jmi-flagship-project::lessons`, `imc-prosperity-4-agentic-autoresearch::approach` |
| `cross-data-engineering-postgres` | en | 0.333 | 0.333 | 0.235 | `car-price-prediction-dsc-pjatk::approach`, `engineering-thesis-btc-signal-prediction::impact`, `jmi-flagship-project::approach`, `engineering-thesis-btc-signal-prediction::context`, `red-ocean-junior-java-developer::approach` |
| `cross-quant-finance` | en | 0.400 | 1.000 | 0.509 | `volatility-surface-coding-jesus-feature::context`, `engineering-thesis-btc-signal-prediction::impact`, `engineering-thesis-btc-signal-prediction::approach`, `volatility-surface-coding-jesus-feature::impact`, `imc-prosperity-4-agentic-autoresearch::impact` |
| `cross-junior-java-oop` | en | 0.500 | 0.333 | 0.346 | `red-ocean-junior-java-developer::lessons`, `red-ocean-junior-java-developer::context`, `red-ocean-junior-java-developer::approach`, `red-ocean-junior-java-developer::impact`, `quantfolio-javafx-portfolio-simulator::approach` |
| `pl-java-spring-backend` | pl | 0.667 | 1.000 | 0.765 | `red-ocean-junior-java-developer::approach`, `red-ocean-junior-java-developer::context`, `red-ocean-junior-java-developer::lessons`, `hackyeah-2025-transport-tracker::approach`, `jmi-flagship-project::lessons` |
| `pl-ml-pytorch` | pl | 0.750 | 1.000 | 0.710 | `bus-punctuality-neural-network::approach`, `pjatk-data-science-club-membership::approach`, `bus-punctuality-neural-network::lessons`, `bus-punctuality-neural-network::context`, `bus-punctuality-neural-network::impact` |
| `pl-junior-backend-python` | pl | 0.667 | 1.000 | 0.671 | `hackyeah-2025-transport-tracker::approach`, `jmi-flagship-project::impact`, `red-ocean-junior-java-developer::approach`, `jmi-flagship-project::approach`, `red-ocean-junior-java-developer::lessons` |
| `edge-vague-fast-learner` | en | 0.250 | 0.500 | 0.246 | `imc-prosperity-4-agentic-autoresearch::impact`, `imc-prosperity-4-agentic-autoresearch::lessons`, `imc-prosperity-4-agentic-autoresearch::approach`, `jmi-flagship-project::context`, `jmi-flagship-project::approach` |
| `edge-ambiguous-trading-bot` | en | 0.400 | 1.000 | 0.553 | `imc-prosperity-4-agentic-autoresearch::context`, `imc-prosperity-4-agentic-autoresearch::approach`, `imc-prosperity-4-agentic-autoresearch::lessons`, `imc-prosperity-4-agentic-autoresearch::impact`, `jmi-flagship-project::approach` |

---

**Note on CIs:** this script computes means only. Bootstrap CIs are
computed offline by feeding the per-query vectors into
`jmi.evaluation.retrieval_metrics.bootstrap_ci` (or, for paired
comparison, `paired_bootstrap_ci`). See ADR-0015 §benchmark.
