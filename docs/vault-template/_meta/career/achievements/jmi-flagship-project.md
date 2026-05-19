---
type: achievement
title: Job Market Intelligence — Portfolio Flagship Project
skills:
  - data engineering
  - LLM application development
  - software architecture
  - API design
  - technical writing
tech_stack:
  - Python
  - PostgreSQL
  - pgvector
  - SQLAlchemy
  - FastAPI
  - Typer
  - Docker
  - Chrome extension (MV3)
seniority_relevance:
  - junior
  - mid
  - senior
impact_metrics:
  - "[TODO: number of job postings ingested and analyzed to date]"
  - "[TODO: external signal — feedback, GitHub interest, an interview discussion]"
keywords:
  - data pipeline
  - retrieval-augmented generation
  - LLM application
  - portfolio project
---

## Context

Job Market Intelligence (JMI) is my flagship portfolio project: a Polish AI/ML
job-market pipeline that ingests job postings, extracts structured data from
them with an LLM, stores everything in Postgres, and runs analytics on top. It
is both a working personal tool and the centrepiece of my AI Engineer job
applications.

## Approach

JMI is built in phases. Phase 1 is terms-of-service-clean ingestion from three
sources — a Hugging Face API scraper plus a human-in-the-loop Chrome extension
for portals whose terms forbid server-side scraping. Phase 2 is an analytics
proof of concept: sentence-transformer embeddings, KMeans clustering, and a
generated market report. Phase 3, in progress, is a retrieval-augmented résumé
generator. Every non-trivial decision is captured as an architecture decision
record (ADR). [TODO: add the one design choice or hard problem you are most
proud of.]

## Impact

[TODO: the concrete state of the project — how much data it holds, what the
analytics surface, and whether you use it for your own job search.] [TODO: any
external signal — feedback you received, or an interview where it came up.]

## What I learned

[TODO: the biggest lesson — about scoping a long multi-phase project, about the
terms-of-service research that reshaped the ingestion design, or about building
a system with an LLM in the loop.]
