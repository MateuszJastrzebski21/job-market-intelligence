"""Tests for the LangChain cross-encoder reranker.

DB-free, model-free: a fake `BaseCrossEncoder` produces deterministic scores and
asserts that CrossEncoderReranker re-sorts and truncates to top_n. The model
loading path itself is exercised in marked-slow integration tests.
"""

from langchain.retrievers.document_compressors.cross_encoder import BaseCrossEncoder
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from jmi.rag_langchain.reranking import (
    RERANKER_MODEL_NAME,
    SentenceTransformersCrossEncoder,
    build_reranker,
    compose_with_reranker,
    compose_without_reranker,
)


class _ConstantCrossEncoder(BaseCrossEncoder):
    """Returns a pre-set score per (query, doc) pair by doc-index."""

    def __init__(self, scores_by_text: dict[str, float]) -> None:
        self._scores = scores_by_text

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        return [self._scores.get(text, 0.0) for _, text in text_pairs]


class _FakeRetriever(BaseRetriever):
    """A retriever that always returns its canned docs in canned order."""

    docs: list[Document]

    def _get_relevant_documents(self, query: str) -> list[Document]:  # type: ignore[override]
        return list(self.docs)


def test_reranker_model_name_is_bge_base() -> None:
    assert RERANKER_MODEL_NAME == "BAAI/bge-reranker-base"


def test_sentence_transformers_cross_encoder_loads_lazily() -> None:
    enc = SentenceTransformersCrossEncoder()
    assert enc._model is None  # no download on construction


def test_sentence_transformers_cross_encoder_empty_pairs_returns_empty() -> None:
    enc = SentenceTransformersCrossEncoder()
    # Empty input must short-circuit without touching the model.
    assert enc.score([]) == []
    assert enc._model is None


def test_build_reranker_uses_default_model() -> None:
    rr = build_reranker(top_n=3)
    assert rr.top_n == 3
    assert isinstance(rr.model, SentenceTransformersCrossEncoder)


def test_compose_with_reranker_changes_order() -> None:
    # Base retriever returns docs in worst-to-best score order; reranker should
    # flip them.
    docs = [
        Document(page_content="worst", metadata={"i": 0}),
        Document(page_content="middle", metadata={"i": 1}),
        Document(page_content="best", metadata={"i": 2}),
    ]
    base = _FakeRetriever(docs=docs)
    encoder = _ConstantCrossEncoder({"worst": 0.1, "middle": 0.5, "best": 0.9})
    composed = compose_with_reranker(base, top_n=3, model=encoder)
    out = composed.invoke("any query")
    assert [d.page_content for d in out] == ["best", "middle", "worst"]


def test_compose_with_reranker_truncates_to_top_n() -> None:
    docs = [Document(page_content=f"doc-{i}", metadata={"i": i}) for i in range(5)]
    base = _FakeRetriever(docs=docs)
    encoder = _ConstantCrossEncoder(
        {"doc-0": 0.1, "doc-1": 0.2, "doc-2": 0.3, "doc-3": 0.4, "doc-4": 0.5}
    )
    composed = compose_with_reranker(base, top_n=2, model=encoder)
    out = composed.invoke("any query")
    assert len(out) == 2
    assert [d.page_content for d in out] == ["doc-4", "doc-3"]


def test_compose_without_reranker_is_identity() -> None:
    base = _FakeRetriever(docs=[Document(page_content="hi", metadata={})])
    assert compose_without_reranker(base) is base
