"""Report-renderer tests: a golden-file snapshot for Markdown and a structural
smoke test for HTML. Regenerate the golden file with `JMI_UPDATE_GOLDEN=1`."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from jmi.analytics.cluster import Cluster, ClusterResult
from jmi.analytics.report import generate_html_report, generate_markdown_report
from jmi.analytics.schemas import JobView

_GOLDEN = Path(__file__).parent / "golden" / "market_report_2026-05-18.md"
_REPORT_DATE = date(2026, 5, 18)


def _fixture() -> tuple[ClusterResult, list[JobView]]:
    """A small, fully deterministic scenario: 6 postings, 3 clusters, two
    sources, mixed extract coverage, and a deliberately low silhouette."""
    ids = [UUID(int=i) for i in range(6)]
    jobs = [
        JobView(posting_id=ids[0], title="Senior ML Engineer",
                source="huggingface", tech_stack=["Python", "PyTorch"]),
        JobView(posting_id=ids[1], title="AI Research Scientist",
                source="huggingface", tech_stack=["Python", "JAX"]),
        JobView(posting_id=ids[2], title="MLOps Engineer",
                source="jjit", tech_stack=["Kubernetes", "Python"]),
        JobView(posting_id=ids[3], title="Data Engineer",
                source="huggingface", tech_stack=[]),
        JobView(posting_id=ids[4], title="Backend Developer",
                source="jjit", tech_stack=[]),
        JobView(posting_id=ids[5], title="Frontend Developer",
                source="huggingface", tech_stack=[]),
    ]
    clusters = [
        Cluster(cluster_id=0, posting_ids=[ids[0], ids[1]],
                centroid=[0.0] * 384, size=2),
        Cluster(cluster_id=1, posting_ids=[ids[2], ids[3]],
                centroid=[0.0] * 384, size=2),
        Cluster(cluster_id=2, posting_ids=[ids[4], ids[5]],
                centroid=[0.0] * 384, size=2),
    ]
    result = ClusterResult(k=3, n_samples=6, silhouette=0.15, clusters=clusters)
    return result, jobs


def test_markdown_report_golden() -> None:
    cluster_result, jobs = _fixture()
    rendered = generate_markdown_report(
        cluster_result, jobs, report_date=_REPORT_DATE
    )
    if os.environ.get("JMI_UPDATE_GOLDEN"):
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN.write_text(rendered, encoding="utf-8")
        pytest.skip("golden file regenerated (JMI_UPDATE_GOLDEN set)")
    assert rendered == _GOLDEN.read_text(encoding="utf-8")


def test_html_report_smoke() -> None:
    cluster_result, jobs = _fixture()
    rendered = generate_html_report(
        cluster_result, jobs, report_date=_REPORT_DATE
    )
    assert "<canvas" in rendered
    assert "https://cdn.jsdelivr.net/npm/chart.js" in rendered
    assert "<body>" in rendered
    assert len(rendered) > 500
    assert "Senior ML Engineer" in rendered
    assert "JMI Market Report — 2026-05-18" in rendered
