# JMI Market Report — 2026-05-18

## Coverage

6 postings clustered. Per-source breakdown:

- huggingface: 4
- jjit: 2

LLM extracts available for 3 of 6 postings — the tech-stack term lists below cover only those.

## Clusters

k = 3 (fixed). KMeans over MiniLM embeddings of posting title + description text.

### Cluster 0 — 2 postings

- Top tech: Python (2), JAX (1), PyTorch (1)
- Sample titles: AI Research Scientist; Senior ML Engineer

### Cluster 1 — 2 postings

- Top tech: Kubernetes (1), Python (1)
- Sample titles: Data Engineer; MLOps Engineer

### Cluster 2 — 2 postings

- Top tech: _no extract data_
- Sample titles: Backend Developer; Frontend Developer

Silhouette: 0.15 — LOW (below the 0.20 warn threshold; clusters weakly separated, expected at small N)

## Caveats

- N = 6 postings — a proof-of-concept sample, not market intelligence at scale.
- k = 3 is fixed (not tuned) as a rough proxy for AI/ML role archetypes; clusters are forced even where structure is weak.
- Tech-stack terms aggregate LLM extracts only — 3 of 6 postings.
- Embeddings use sentence-transformers all-MiniLM-L6-v2 (local, no API cost); semantic quality is adequate for this PoC scale.
- Re-run at N > 50 for the first statistically meaningful clusters.

See [docs/adr/0011-phase2-poc-choices.md](adr/0011-phase2-poc-choices.md) for the rationale behind these choices.
