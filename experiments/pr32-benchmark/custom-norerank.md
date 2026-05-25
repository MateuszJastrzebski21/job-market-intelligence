# Benchmark — `custom-norerank`

- **k:** 5
- **n_queries:** 15
- **seed_version:** 1
- **seed_file:** `docs/ground_truth/rag_retrieval_seed.json`
- **timestamp:** 2026-05-20T16:05:39.672058+00:00
- **config:** `pipeline`=`custom`, `rerank`=`False`

## Aggregate (mean; CIs computed offline via jmi.evaluation.bootstrap_ci)

| Metric | Value |
| --- | --- |
| recall@5 | 0.570 |
| MRR | 0.700 |
| nDCG@5 | 0.550 |

## Per-query breakdown

| query_id | lang | recall@5 | MRR | nDCG@5 | top-5 retrieved |
| --- | --- | --- | --- | --- | --- |
| `single-java-backend` | en | 0.667 | 1.000 | 0.765 | `red-ocean-junior-java-developer::context`, `red-ocean-junior-java-developer::approach`, `red-ocean-junior-java-developer::lessons`, `jmi-flagship-project::approach`, `jmi-flagship-project::impact` |
| `single-quant-options` | en | 1.000 | 1.000 | 0.947 | `volatility-surface-coding-jesus-feature::context`, `volatility-surface-coding-jesus-feature::approach`, `volatility-surface-coding-jesus-feature::lessons`, `engineering-thesis-btc-signal-prediction::context`, `volatility-surface-coding-jesus-feature::impact` |
| `single-llm-agent` | en | 0.667 | 1.000 | 0.765 | `imc-prosperity-4-agentic-autoresearch::approach`, `imc-prosperity-4-agentic-autoresearch::impact`, `imc-prosperity-4-agentic-autoresearch::lessons`, `jmi-flagship-project::approach`, `jmi-flagship-project::context` |
| `single-ml-competition` | en | 0.333 | 0.333 | 0.235 | `engineering-thesis-btc-signal-prediction::approach`, `engineering-thesis-btc-signal-prediction::context`, `car-price-prediction-dsc-pjatk::approach`, `car-price-prediction-dsc-pjatk::lessons`, `jmi-flagship-project::approach` |
| `single-fullstack-fastapi` | en | 0.333 | 1.000 | 0.469 | `hackyeah-2025-transport-tracker::approach`, `jmi-flagship-project::approach`, `jmi-flagship-project::impact`, `red-ocean-junior-java-developer::lessons`, `jmi-flagship-project::context` |
| `cross-python-ml-pytorch` | en | 0.600 | 0.333 | 0.447 | `jmi-flagship-project::impact`, `engineering-thesis-btc-signal-prediction::context`, `bus-punctuality-neural-network::approach`, `car-price-prediction-dsc-pjatk::approach`, `engineering-thesis-btc-signal-prediction::approach` |
| `cross-rest-api-design` | en | 0.750 | 1.000 | 0.805 | `jmi-flagship-project::approach`, `hackyeah-2025-transport-tracker::approach`, `jmi-flagship-project::impact`, `red-ocean-junior-java-developer::impact`, `red-ocean-junior-java-developer::lessons` |
| `cross-data-engineering-postgres` | en | 0.667 | 0.500 | 0.498 | `red-ocean-junior-java-developer::approach`, `jmi-flagship-project::approach`, `car-price-prediction-dsc-pjatk::approach`, `jmi-flagship-project::impact`, `engineering-thesis-btc-signal-prediction::impact` |
| `cross-quant-finance` | en | 0.600 | 1.000 | 0.616 | `volatility-surface-coding-jesus-feature::context`, `quantfolio-javafx-portfolio-simulator::approach`, `volatility-surface-coding-jesus-feature::lessons`, `volatility-surface-coding-jesus-feature::approach`, `engineering-thesis-btc-signal-prediction::approach` |
| `cross-junior-java-oop` | en | 0.500 | 0.333 | 0.346 | `red-ocean-junior-java-developer::lessons`, `red-ocean-junior-java-developer::context`, `quantfolio-javafx-portfolio-simulator::approach`, `railway-logistics-simulation::context`, `red-ocean-junior-java-developer::approach` |
| `pl-java-spring-backend` | pl | 0.667 | 1.000 | 0.765 | `red-ocean-junior-java-developer::context`, `red-ocean-junior-java-developer::approach`, `red-ocean-junior-java-developer::lessons`, `jmi-flagship-project::impact`, `jmi-flagship-project::approach` |
| `pl-ml-pytorch` | pl | 0.500 | 0.500 | 0.441 | `bus-punctuality-neural-network::lessons`, `bus-punctuality-neural-network::impact`, `bus-punctuality-neural-network::context`, `car-price-prediction-dsc-pjatk::lessons`, `pjatk-data-science-club-membership::approach` |
| `pl-junior-backend-python` | pl | 0.667 | 1.000 | 0.651 | `hackyeah-2025-transport-tracker::approach`, `red-ocean-junior-java-developer::context`, `jmi-flagship-project::impact`, `red-ocean-junior-java-developer::impact`, `jmi-flagship-project::approach` |
| `edge-vague-fast-learner` | en | 0.000 | 0.000 | 0.000 | `red-ocean-junior-java-developer::lessons`, `engineering-thesis-btc-signal-prediction::context`, `jmi-flagship-project::approach`, `railway-logistics-simulation::context`, `bus-punctuality-neural-network::context` |
| `edge-ambiguous-trading-bot` | en | 0.600 | 0.500 | 0.491 | `imc-prosperity-4-agentic-autoresearch::impact`, `engineering-thesis-btc-signal-prediction::context`, `jmi-flagship-project::approach`, `imc-prosperity-4-agentic-autoresearch::approach`, `imc-prosperity-4-agentic-autoresearch::context` |

---

**Note on CIs:** this script computes means only. Bootstrap CIs are
computed offline by feeding the per-query vectors into
`jmi.evaluation.retrieval_metrics.bootstrap_ci` (or, for paired
comparison, `paired_bootstrap_ci`). See ADR-0015 §benchmark.
