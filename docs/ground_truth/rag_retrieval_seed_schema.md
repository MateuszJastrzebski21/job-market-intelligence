# RAG Retrieval Golden Set — Seed Schema

**Status:** Draft — schema only, no data yet (audit H5 / E-2).

This document specifies the structure of
`docs/ground_truth/rag_retrieval_seed.json`, the golden set for Phase 3
retrieval evaluation. The JSON file itself and its Pydantic validator land in
PR-3.2; the schema is recorded now so the Achievement schema (ADR-0014) and the
retrieval-metrics skeleton (`src/jmi/evaluation/retrieval_metrics.py`) agree on
one contract before either is implemented.

## Purpose

Retrieval quality must be measurable from the first RAG PR. Each seed entry
pairs a **query** (a job posting or a role description) with the achievement
**chunks** that *should* be retrieved for it. `retrieval_metrics.py` scores a
retriever's actual output against these entries with recall@k, MRR, and nDCG.

## File shape

`rag_retrieval_seed.json` is a JSON object — a version string and a list of
entries:

```json
{
  "version": "1",
  "entries": [ { "...one entry..." } ]
}
```

## Entry fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | string | yes | Stable identifier for the entry. |
| `query` | string | yes | The job-posting text or role description to retrieve for. |
| `relevant_chunk_ids` | list of string | yes | Achievement chunk ids that should be retrieved. Drives recall@k and MRR. |
| `graded_relevance` | object (string → number) | no | Optional per-chunk relevance grades for nDCG. Chunk ids absent from the map score 0. |
| `notes` | string | no | Free-text rationale for the labelling. |

## Conventions

- A chunk id refers to a row in the `achievement_embeddings` table (ADR-0014)
  — durable and queryable, so a seed entry stays valid across re-ingests.
- When both are present, `relevant_chunk_ids` must be a subset of the keys of
  `graded_relevance`.
- At least ~10 entries must exist before the Phase 3 RAG MVP merges (E-2).

## Open questions for PR-3.2

- Whether `query` stores posting text inline or references a `job_postings` row.
- The grade scale for `graded_relevance` — binary, 0–3, or continuous 0–1.
