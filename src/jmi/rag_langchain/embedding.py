"""LangChain HuggingFaceEmbeddings adapter for BAAI/bge-small-en-v1.5.

The wrapper is intentionally thin — `langchain-huggingface`'s HuggingFaceEmbeddings
already exposes the two-method `Embeddings` ABC (embed_documents, embed_query). We
configure it once and re-expose a typed factory + the constant the rest of the package
needs (model name, dimension), so callers depend on `get_embeddings()` rather than
the raw HF wrapper class. This matches Worktree A's `CustomEmbedder` API surface.

Model: bge-small-en-v1.5 — 384-dim, drops into the existing Vector(384) column
(dossier §2, ADR-0011). Asymmetric retrieval needs no instruction prefix for bge-small
in 1.5+ (BGE-large used to; bge-small/base/v1.5 do not). Embeddings normalized via the
model-default L2 inside sentence-transformers.
"""

from typing import TYPE_CHECKING

from langchain_huggingface import HuggingFaceEmbeddings

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


_embeddings: HuggingFaceEmbeddings | None = None


def get_embeddings() -> "Embeddings":
    """Return the process-wide HuggingFaceEmbeddings instance, loading on first call.

    Lazy — importing this module must not download the model (~130 MB) or import
    torch. Unit tests monkeypatch this function with a fake `Embeddings`.
    """
    global _embeddings
    if _embeddings is None:
        # HuggingFaceEmbeddings already owns `show_progress` — passing
        # show_progress_bar via encode_kwargs collides with its own injection
        # (TypeError "multiple values for keyword argument").
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            encode_kwargs={"normalize_embeddings": True},
            show_progress=False,
        )
    return _embeddings
