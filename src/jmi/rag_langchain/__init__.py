"""LangChain reimplementation of the Phase 3 RAG retrieval pipeline (PR-3.2, Worktree B).

This package mirrors the public surface of `jmi.rag` (custom implementation, Worktree A)
so the same benchmark harness can evaluate both side-by-side. Decisions are recorded
in ADR-0015b. The pipeline is intentionally idiomatic LangChain — chunks emitted as
`Document`, retrieval through `BaseRetriever`, reranking via `ContextualCompressionRetriever`,
generation via an LCEL chain — so the comparison surface is the framework's, not a
custom shim wrapped in LangChain class names.
"""
