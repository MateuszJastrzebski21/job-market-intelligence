from uuid import UUID

import numpy as np
import structlog
from pydantic import BaseModel, ConfigDict

from jmi.analytics.cluster import ClusterResult, cluster_postings
from jmi.analytics.embed import EmbedRequest, embed
from jmi.analytics.schemas import JobView
from jmi.storage.jobs import JobExtractRepository, JobPostingRepository

log = structlog.get_logger(__name__)


class AnalysisBundle(BaseModel):
    """Report inputs produced by `run_analysis`: the clustering result plus the
    per-posting views the report draws from."""

    model_config = ConfigDict(extra="forbid")

    cluster_result: ClusterResult
    jobs: list[JobView]


def _embed_text(title: str, description_text: str) -> str:
    """Embedding input for one posting: title first (highest signal density,
    and MiniLM truncates beyond 256 tokens), then the description body."""
    return f"{title}\n\n{description_text}"


def _tech_stack_by_posting(
    extract_repo: JobExtractRepository,
) -> dict[UUID, list[str]]:
    """Map each posting to the tech_stack of its most recent extract."""
    by_posting: dict[UUID, list[str]] = {}
    # list_all() returns extracts newest-first, so the first seen per posting wins.
    for extract in extract_repo.list_all(limit=10_000):
        by_posting.setdefault(extract.job_posting_id, extract.tech_stack)
    return by_posting


def run_analysis(
    posting_repo: JobPostingRepository,
    extract_repo: JobExtractRepository,
    *,
    skip_embed: bool,
) -> AnalysisBundle:
    """Embed postings, cluster them, and assemble the report inputs.

    With ``skip_embed=False`` every posting that has description text is
    embedded and the vectors are persisted. With ``skip_embed=True`` the
    vectors already stored in the DB are reused. Raises ValueError when there
    is nothing to work with.
    """
    if skip_embed:
        pairs = posting_repo.list_with_embeddings()
        if not pairs:
            raise ValueError(
                "no stored embeddings found — run `jmi analyze` without --skip-embed first"
            )
        postings = [posting for posting, _ in pairs]
        embeddings = np.array([vector for _, vector in pairs], dtype=np.float32)
        log.info("reusing stored embeddings", count=len(postings))
    else:
        postings = posting_repo.list_embeddable()
        if not postings:
            raise ValueError("no postings with description text to embed")
        texts = [_embed_text(p.title, p.description_text or "") for p in postings]
        embeddings = embed(EmbedRequest(texts=texts)).vectors
        for posting, vector in zip(postings, embeddings, strict=True):
            posting_repo.store_embedding(posting.id, vector)
        log.info("embedded postings", count=len(postings))

    cluster_result = cluster_postings(embeddings, [p.id for p in postings])

    tech_by_posting = _tech_stack_by_posting(extract_repo)
    jobs = [
        JobView(
            posting_id=p.id,
            title=p.title,
            source=p.source,
            tech_stack=tech_by_posting.get(p.id, []),
        )
        for p in postings
    ]
    return AnalysisBundle(cluster_result=cluster_result, jobs=jobs)
