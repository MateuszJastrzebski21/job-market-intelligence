"""Clustering tests. Synthetic embeddings with a fixed RNG seed so KMeans is
fully deterministic."""
from __future__ import annotations

from uuid import uuid4

import numpy as np
import pytest
from structlog.testing import capture_logs

from jmi.analytics.cluster import cluster_postings


def _blobs(seed: int = 42) -> tuple[np.ndarray, list[int]]:
    """Three tight, well-separated blobs of 5 points each in 384-dim space."""
    rng = np.random.default_rng(seed)
    dim = 384
    points: list[np.ndarray] = []
    true_labels: list[int] = []
    for axis in range(3):
        center = np.zeros(dim, dtype=np.float32)
        center[axis] = 10.0
        for _ in range(5):
            points.append(center + rng.normal(0, 0.1, dim).astype(np.float32))
            true_labels.append(axis)
    return np.array(points, dtype=np.float32), true_labels


def test_kmeans_recovers_known_clusters() -> None:
    embeddings, true_labels = _blobs()
    ids = [uuid4() for _ in true_labels]
    true_by_id = dict(zip(ids, true_labels, strict=True))

    result = cluster_postings(embeddings, ids, k=3)

    assert result.n_samples == 15
    assert sorted(c.size for c in result.clusters) == [5, 5, 5]
    # each recovered cluster is pure: all members share one ground-truth label
    for cluster in result.clusters:
        assert len({true_by_id[pid] for pid in cluster.posting_ids}) == 1
    assert result.silhouette > 0.5


def test_silhouette_logged_at_info_when_well_separated() -> None:
    embeddings, true_labels = _blobs()
    ids = [uuid4() for _ in true_labels]
    with capture_logs() as logs:
        cluster_postings(embeddings, ids, k=3)
    events = [e for e in logs if e.get("event") == "clustering complete"]
    assert len(events) == 1
    assert "silhouette" in events[0]
    assert events[0]["log_level"] == "info"


def test_low_silhouette_logged_above_info() -> None:
    rng = np.random.default_rng(0)
    embeddings = rng.random((20, 384), dtype=np.float32)  # no real structure
    ids = [uuid4() for _ in range(20)]
    with capture_logs() as logs:
        result = cluster_postings(embeddings, ids, k=6)
    events = [e for e in logs if e.get("event") == "clustering complete"]
    assert events[0]["log_level"] in {"warning", "error"}
    assert result.silhouette < 0.2


def test_too_few_samples_raises() -> None:
    embeddings = np.zeros((3, 384), dtype=np.float32)
    ids = [uuid4() for _ in range(3)]
    with pytest.raises(ValueError, match="need more than"):
        cluster_postings(embeddings, ids, k=3)


def test_length_mismatch_raises() -> None:
    embeddings = np.zeros((5, 384), dtype=np.float32)
    ids = [uuid4() for _ in range(3)]
    with pytest.raises(ValueError, match="length mismatch"):
        cluster_postings(embeddings, ids, k=2)
