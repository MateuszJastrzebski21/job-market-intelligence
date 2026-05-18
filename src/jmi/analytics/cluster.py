from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import numpy as np
import structlog
from pydantic import BaseModel, ConfigDict
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

log = structlog.get_logger(__name__)

KMEANS_K = 6
SILHOUETTE_WARN = 0.2
SILHOUETTE_ERROR = 0.1
RANDOM_STATE = 42


class Cluster(BaseModel):
    """One KMeans cluster: its member postings and centroid."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int
    posting_ids: list[UUID]
    centroid: list[float]
    size: int


class ClusterResult(BaseModel):
    """Outcome of clustering a batch of posting embeddings."""

    model_config = ConfigDict(extra="forbid")

    k: int
    n_samples: int
    silhouette: float
    clusters: list[Cluster]


def cluster_postings(
    embeddings: np.ndarray,
    posting_ids: Sequence[UUID],
    *,
    k: int = KMEANS_K,
) -> ClusterResult:
    """Partition posting embeddings into ``k`` clusters with KMeans.

    Pure function — no DB access; ``posting_ids`` are passed in so the result
    can name its members. Deterministic (fixed ``random_state``). The
    silhouette score is logged: a warning below 0.2, an error below 0.1 — the
    PoC keeps running either way (see ADR-0011).

    Raises ValueError when there are too few samples: KMeans needs N > k and
    the silhouette score needs k <= N - 1.
    """
    n_samples = int(embeddings.shape[0])
    if n_samples != len(posting_ids):
        raise ValueError(
            f"embeddings/posting_ids length mismatch: {n_samples} vs {len(posting_ids)}"
        )
    if n_samples <= k:
        raise ValueError(
            f"need more than k={k} postings to cluster, got {n_samples}; "
            "ingest more data or lower k"
        )

    model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    labels = model.fit_predict(embeddings)
    silhouette = float(silhouette_score(embeddings, labels))

    ids = list(posting_ids)
    clusters = [
        Cluster(
            cluster_id=cluster_id,
            posting_ids=[ids[i] for i in range(n_samples) if labels[i] == cluster_id],
            centroid=[float(x) for x in model.cluster_centers_[cluster_id]],
            size=int((labels == cluster_id).sum()),
        )
        for cluster_id in range(k)
    ]

    fields = {"k": k, "n_samples": n_samples, "silhouette": round(silhouette, 4)}
    if silhouette < SILHOUETTE_ERROR:
        log.error("clustering complete", **fields)
    elif silhouette < SILHOUETTE_WARN:
        log.warning("clustering complete", **fields)
    else:
        log.info("clustering complete", **fields)

    return ClusterResult(k=k, n_samples=n_samples, silhouette=silhouette, clusters=clusters)
