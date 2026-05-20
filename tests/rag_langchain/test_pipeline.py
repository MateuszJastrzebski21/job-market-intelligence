"""Tests for the LangChain RagPipeline composition.

The pipeline is a thin composer of already-tested parts — these tests focus on
the with/without-rerank branches, the public method signatures matching
Worktree A's contract, and the fact that the generation chain is the one we
inject (no live API calls).
"""

from typing import Any

from langchain_core.documents import Document
from langchain_core.runnables import Runnable

from jmi.rag_langchain.pipeline import RagPipeline


class _FakeStore:
    """Stand-in for PGVectorStore with three docs and a deterministic distance scale."""

    def __init__(self) -> None:
        self.docs = [
            Document(
                page_content=f"chunk-{i} body",
                metadata={
                    "langchain_id": f"id-{i}",
                    "achievement_id": f"a-{i}",
                    "chunk_index": i,
                    "section": "impact" if i == 0 else "lessons",
                    "title": f"Achievement {i}",
                },
            )
            for i in range(3)
        ]
        self.last_query: str | None = None
        self.last_k: int | None = None

    def similarity_search_with_score(self, query: str, k: int = 5) -> list[tuple[Document, float]]:
        self.last_query = query
        self.last_k = k
        return [(d, 0.1 + i * 0.1) for i, d in enumerate(self.docs[:k])]

    def as_retriever(self, *, search_kwargs: dict[str, Any]) -> "_FakeBaseRetriever":
        k = int(search_kwargs.get("k", 5))
        return _FakeBaseRetriever(docs=self.docs[:k])


class _FakeBaseRetriever:
    """Mimics a LangChain BaseRetriever for the reranker compose path."""

    def __init__(self, docs: list[Document]) -> None:
        self.docs = docs

    def invoke(self, query: str) -> list[Document]:
        return self.docs


class _CapturingChain(Runnable[dict[str, object], str]):
    def __init__(self, response: str = "- one\n- two") -> None:
        self.response = response
        self.last_input: dict[str, object] | None = None

    def invoke(self, input: dict[str, object], config: Any = None, **kwargs: Any) -> str:
        self.last_input = input
        return self.response


def test_pipeline_retrieve_without_rerank_returns_scored_chunks() -> None:
    fake_store = _FakeStore()
    pipeline = RagPipeline(store=fake_store, generation_chain=_CapturingChain())  # type: ignore[arg-type]
    result = pipeline.retrieve_top_k("query", k=2, rerank=False)
    assert len(result) == 2
    assert result[0].chunk_id == "id-0"
    assert result[0].chunk_text == "chunk-0 body"
    assert result[0].score > result[1].score


def test_pipeline_generate_uses_provided_chain() -> None:
    fake_store = _FakeStore()
    chain = _CapturingChain(response="- bullet")
    pipeline = RagPipeline(store=fake_store, generation_chain=chain)  # type: ignore[arg-type]
    out = pipeline.generate_bullets("the JD body", k=2, rerank=False)
    assert out == "- bullet"
    assert chain.last_input is not None
    assert chain.last_input["job_description"] == "the JD body"
    assert chain.last_input["k"] == 2


def test_pipeline_generate_with_rerank_false_skips_compression(monkeypatch: Any) -> None:
    """rerank=False must NOT call compose_with_reranker."""
    fake_store = _FakeStore()
    chain = _CapturingChain()
    pipeline = RagPipeline(store=fake_store, generation_chain=chain)  # type: ignore[arg-type]

    called = {"yes": False}

    def _fake_compose(*args: Any, **kwargs: Any) -> object:
        called["yes"] = True
        return None

    monkeypatch.setattr("jmi.rag_langchain.pipeline.compose_with_reranker", _fake_compose)

    pipeline.generate_bullets("jd", k=2, rerank=False)
    assert called["yes"] is False
