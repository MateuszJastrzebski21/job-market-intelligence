# JMI Market Report — 2026-05-18

## Coverage

18 postings clustered. Per-source breakdown:

- huggingface: 2
- jjit: 16

LLM extracts available for 7 of 18 postings — the tech-stack term lists below cover only those.

## Clusters

k = 6 (fixed). KMeans over MiniLM embeddings of posting title + description text.

### Cluster 0 — 3 postings

- Top tech: _no extract data_
- Sample titles: AI Engineer; MLOps Engineer; Machine Learning Engineer

### Cluster 1 — 3 postings

- Top tech: GenAI (1), NLP (1), Python (1)
- Sample titles: AI Engineer (Agentic Systems); AI Engineer (K/M); LLM Engineer  (RAG, Agents, Graph AI)

### Cluster 2 — 6 postings

- Top tech: Python (2), Angular (1), Azure (1), Claude Code (1), Cursor (1), Databricks (1), GCP (1), Hugging Face (1)
- Sample titles: AI Specialist – GenAI &Agentic Systems; Agentic AI Engineer – Mid/Senior; Data Scientist (GenAI / Agentic Systems)

### Cluster 3 — 3 postings

- Top tech: _no extract data_
- Sample titles: AI Business Analyst/AI Consultant; ML Engineer (Regular); Machine Learning Operations Section Manager (m/f/d)

### Cluster 4 — 1 posting

- Top tech: Argo Workflows (1), BigQuery (1), GCP (1), Kubernetes (1), NumPy (1), Pandas (1), Prefect (1), PyTorch (1)
- Sample titles: Machine Learning Infrastructure Engineer

### Cluster 5 — 2 postings

- Top tech: AWS (2), Azure (2), Cloudflare (2), GCP (2), NVIDIA CUDA (2), PyTorch (2), Python (2)
- Sample titles: Cloud ML DevRel Engineer - EMEA remote; Cloud ML DevRel Engineer - US remote

Silhouette: 0.18 — LOW (below the 0.20 warn threshold; clusters weakly separated, expected at small N)

## Caveats

- N = 18 postings — a proof-of-concept sample, not market intelligence at scale.
- k = 6 is fixed (not tuned) as a rough proxy for AI/ML role archetypes; clusters are forced even where structure is weak.
- Tech-stack terms aggregate LLM extracts only — 7 of 18 postings.
- Embeddings use sentence-transformers all-MiniLM-L6-v2 (local, no API cost); semantic quality is adequate for this PoC scale.
- Re-run at N > 50 for the first statistically meaningful clusters.

See [docs/adr/0011-phase2-poc-choices.md](adr/0011-phase2-poc-choices.md) for the rationale behind these choices.
