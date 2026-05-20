"""Phase 3 RAG package — chunking, embeddings, retrieval, reranking, generation.

The package implements PR-3.2's custom RAG pipeline (ADR-0015a):

- ``chunking`` — per-section chunker over the ``Achievement`` domain model
- ``embedding`` — BGE-small-en-v1.5 sentence-transformers wrapper
- ``ingest`` — chunk → embed → upsert pipeline into ``achievement_embeddings``
- ``retrieval`` — pgvector cosine-similarity retriever
- ``reranking`` — bge-reranker-base cross-encoder, drop-in optional stage
- ``pipeline`` — composed retrieve→rerank entry point
- ``generation`` — Anthropic Claude bullet generator

H1/S-2 applies throughout: log identifiers, lengths, counts — never chunk text.
"""
