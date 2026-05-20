"""Cross-encoder reranking via LangChain's ContextualCompressionRetriever.

LangChain's `CrossEncoderReranker` takes any `BaseCrossEncoder` (`score(pairs)
-> list[float]`). The companion `langchain-community.HuggingFaceCrossEncoder`
is the canonical adapter, but it would force pulling in `langchain-community`
(a heavy meta-package) just for one class. Instead, we expose a tiny
`SentenceTransformersCrossEncoder` that wraps the existing
`sentence-transformers.CrossEncoder` — sentence-transformers is already a JMI
dependency, so there is no new install cost.

`CrossEncoderReranker(model=..., top_n=K)` then plugs into
`ContextualCompressionRetriever(base_compressor=..., base_retriever=...)` as
the standard LangChain composition.

Drop-in semantics: callers wanting the unranked path skip the reranker entirely
and use the retriever from T5 directly. `compose_with_reranker` builds the
composed retriever; `compose_without_reranker` is the identity case for
benchmarks that compare ranked vs unranked.

Security (S-2): logs counts and query length, never chunk text.
"""

from typing import TYPE_CHECKING

import structlog
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain.retrievers.document_compressors.cross_encoder import BaseCrossEncoder

if TYPE_CHECKING:
    from langchain_core.retrievers import BaseRetriever
    from sentence_transformers import CrossEncoder

RERANKER_MODEL_NAME = "BAAI/bge-reranker-base"


class SentenceTransformersCrossEncoder(BaseCrossEncoder):
    """Adapter so a sentence-transformers CrossEncoder satisfies BaseCrossEncoder.

    The model is loaded lazily on first `score(...)` call so importing this
    module never triggers a ~280 MB download. Tests pass in a fake encoder.
    """

    def __init__(self, model_name: str = RERANKER_MODEL_NAME) -> None:
        self._model_name = model_name
        self._model: CrossEncoder | None = None

    def _load_model(self) -> "CrossEncoder":
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        if not text_pairs:
            return []
        model = self._load_model()
        # CrossEncoder.predict returns a numpy array; tolist() narrows to floats.
        raw = model.predict(list(text_pairs))
        return [float(x) for x in raw.tolist()]


log = structlog.get_logger(__name__)


def build_reranker(
    top_n: int = 5,
    model: BaseCrossEncoder | None = None,
) -> CrossEncoderReranker:
    """Construct the CrossEncoderReranker — the LangChain document compressor.

    Defaults to `SentenceTransformersCrossEncoder(bge-reranker-base)`; pass an
    explicit `model` to override (tests do this).
    """
    return CrossEncoderReranker(model=model or SentenceTransformersCrossEncoder(), top_n=top_n)


def compose_with_reranker(
    base_retriever: "BaseRetriever",
    top_n: int = 5,
    model: BaseCrossEncoder | None = None,
) -> ContextualCompressionRetriever:
    """Compose `base_retriever` with a CrossEncoderReranker."""
    reranker = build_reranker(top_n=top_n, model=model)
    composed = ContextualCompressionRetriever(
        base_compressor=reranker, base_retriever=base_retriever
    )
    reranker_model = getattr(reranker.model, "_model_name", RERANKER_MODEL_NAME)
    log.info("rag.lc.reranker.composed", reranker_model=reranker_model, top_n=top_n)
    return composed


def compose_without_reranker(base_retriever: "BaseRetriever") -> "BaseRetriever":
    """Identity path — return the retriever unchanged.

    Exists so the pipeline `with_reranker=False` branch is a single function
    swap rather than an if-statement scattered through `pipeline.py`.
    """
    return base_retriever
