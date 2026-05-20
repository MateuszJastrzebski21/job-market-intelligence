# PR-3.2 Custom-RAG Smoke Check

Manual qualitative spot-check of the custom retrieval + generation pipeline
against five sample job descriptions. Five JDs cover:

- AI Engineer (English)
- Junior Backend Java Developer (Polish)
- Quant Researcher (English)
- ML Engineer (English)
- Data Engineer (Polish)

For each JD, the harness runs:

1. `RagPipeline.retrieve_top_k(query=jd, k=5, rerank=True)` against the 44
   achievement chunks in the dev DB.
2. `Generator.generate_bullets(jd, chunks)` against the retrieved chunks.

Outputs are saved as `smoke-{slug}.md` files in this directory. Each file
records:

- The input job description.
- The top-5 retrieved chunks (header line + similarity score).
- The generated bullets, verbatim, with their `(chunks: N, M)` citations.
- A "Notes" section the operator fills in during morning review.

The operator labels each bullet as **grounded / partial / hallucinated**
when they review, which feeds the smoke-check assessment row of ADR-0015.

## How to regenerate

```bash
uv run python experiments/pr32-smoke-check/custom/run.py
```

The script overwrites `smoke-{slug}.md`. Outputs are not deterministic —
Claude's sampling varies run-to-run — but the retrieval order is
deterministic for the same DB state.
