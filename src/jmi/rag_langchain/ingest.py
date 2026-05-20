"""Ingest Achievement chunks into a LangChain-owned pgvector collection.

Per ADR-0015b, Worktree B does NOT share `achievement_embeddings` with the custom
implementation — PGVectorStore owns its own schema. The collection lives in a
sibling table `langchain_achievement_embeddings` on the same database, so both
custom and LangChain stacks coexist without one stomping the other. Storing the
chunk text twice (once in each table) at ~120 KB total for the corpus is the
acceptable cost (PLAN.md, ADR-0015b §4).

Idempotency: deterministic chunk ids derived from `(achievement_id, chunk_index)`
let `add_documents` upsert — re-ingesting the same achievement replaces its
chunks rather than appending duplicates.

Security (S-2): logging here uses ids and counts only, never chunk_text.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

import structlog
from langchain_postgres import PGEngine, PGVectorStore
from sqlalchemy.exc import ProgrammingError

from jmi.config import get_settings
from jmi.models.achievement import Achievement
from jmi.rag_langchain.chunking import chunk_achievements
from jmi.rag_langchain.embedding import EMBEDDING_DIM, get_embeddings

if TYPE_CHECKING:
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings

log = structlog.get_logger(__name__)

COLLECTION_TABLE = "langchain_achievement_embeddings"

# A stable namespace so the same (achievement_id, chunk_index) always produces the
# same deterministic doc UUID — makes ingest idempotent without an extra lookup.
_DOC_ID_NAMESPACE = UUID("c0ffee00-0000-4000-8000-000000000001")


def _doc_id(achievement_id: str, chunk_index: int) -> str:
    return str(uuid5(_DOC_ID_NAMESPACE, f"{achievement_id}:{chunk_index}"))


def get_pg_engine(database_url: str | None = None) -> PGEngine:
    """Construct a PGEngine from the application's database settings.

    The url is the application's standard psycopg/SQLAlchemy DSN; PGEngine accepts
    SQLAlchemy URLs directly.
    """
    url = database_url or get_settings().database_url
    return PGEngine.from_connection_string(url=url)


def ensure_collection_table(engine: PGEngine) -> None:
    """Idempotently create the langchain_achievement_embeddings table.

    `PGEngine.init_vectorstore_table(overwrite_existing=False)` *raises* on
    duplicate (it does not mean "skip"), so for genuine idempotency we
    catch DuplicateTable and treat it as success. The schema is LangChain's
    default: langchain_id (UUID PK), content (text), embedding (vector(384)),
    langchain_metadata (JSONB) — the schema-ownership story ADR-0015b documents.
    """
    try:
        engine.init_vectorstore_table(
            table_name=COLLECTION_TABLE,
            vector_size=EMBEDDING_DIM,
            overwrite_existing=False,
        )
        log.info("rag.lc.collection.ready", table=COLLECTION_TABLE, dim=EMBEDDING_DIM)
    except ProgrammingError as exc:
        # psycopg.errors.DuplicateTable wrapped by SQLAlchemy — already exists.
        if "DuplicateTable" not in str(type(exc.orig).__name__) and "already exists" not in str(
            exc.orig
        ):
            raise
        log.info("rag.lc.collection.exists", table=COLLECTION_TABLE, dim=EMBEDDING_DIM)


def get_vector_store(engine: PGEngine, embeddings: "Embeddings | None" = None) -> PGVectorStore:
    """Bind a PGVectorStore to the existing langchain_achievement_embeddings table.

    The table must already exist (call `ensure_collection_table` first). The
    embeddings instance is the one returned by `get_embeddings()` unless overridden
    — useful for tests that monkeypatch with a fake.
    """
    return PGVectorStore.create_sync(
        engine=engine,
        embedding_service=embeddings or get_embeddings(),
        table_name=COLLECTION_TABLE,
    )


def chunks_to_ids(documents: Sequence["Document"]) -> list[str]:
    """Compute the deterministic langchain_id for each chunk Document."""
    return [
        _doc_id(d.metadata["achievement_id"], int(d.metadata["chunk_index"])) for d in documents
    ]


def ingest_chunks(
    store: PGVectorStore,
    achievements: Sequence[Achievement],
) -> int:
    """Chunk a list of achievements and upsert their embeddings into the store.

    Returns the count of chunks written. Idempotent — re-running with the same
    achievements replaces (rather than appends) their chunks because the doc ids
    are deterministic. Embedding happens inside store.add_documents.
    """
    if not achievements:
        log.info("rag.lc.ingest.empty")
        return 0
    documents = chunk_achievements(achievements)
    ids = chunks_to_ids(documents)
    store.add_documents(documents, ids=ids)
    log.info(
        "rag.lc.ingest.done",
        achievement_count=len(achievements),
        chunk_count=len(documents),
    )
    return len(documents)
