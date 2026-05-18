"""Tests for the `jmi analyze` CLI command.

Kept DB-free by monkeypatching get_session and run_analysis — the same pattern
as tests/evaluation/test_cli.py. The report renderers run for real against a
canned AnalysisBundle, so the test also exercises file output end to end.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from typer.testing import CliRunner

import jmi.analytics.runner as runner_mod
import jmi.db.base as db_base
from jmi.analytics.cluster import Cluster, ClusterResult
from jmi.analytics.runner import AnalysisBundle
from jmi.analytics.schemas import JobView
from jmi.cli import app

cli = CliRunner()


@contextmanager
def _fake_session() -> Iterator[object]:
    yield object()


def _bundle() -> AnalysisBundle:
    """A small, realistic AnalysisBundle the report renderers can format."""
    ids = [UUID(int=i) for i in range(4)]
    jobs = [
        JobView(
            posting_id=ids[0], title="ML Engineer", source="huggingface", tech_stack=["Python"]
        ),
        JobView(
            posting_id=ids[1],
            title="Data Scientist",
            source="huggingface",
            tech_stack=["Python", "SQL"],
        ),
        JobView(posting_id=ids[2], title="MLOps Engineer", source="jjit", tech_stack=["Docker"]),
        JobView(posting_id=ids[3], title="AI Researcher", source="jjit", tech_stack=[]),
    ]
    clusters = [
        Cluster(cluster_id=0, posting_ids=[ids[0], ids[1]], centroid=[0.0] * 384, size=2),
        Cluster(cluster_id=1, posting_ids=[ids[2], ids[3]], centroid=[0.0] * 384, size=2),
    ]
    result = ClusterResult(k=2, n_samples=4, silhouette=0.3, clusters=clusters)
    return AnalysisBundle(cluster_result=result, jobs=jobs)


def _patch(monkeypatch, recorder: dict) -> None:
    monkeypatch.setattr(db_base, "get_session", _fake_session)

    def fake_run_analysis(posting_repo, extract_repo, *, skip_embed):
        recorder["skip_embed"] = skip_embed
        return _bundle()

    monkeypatch.setattr(runner_mod, "run_analysis", fake_run_analysis)


def test_analyze_writes_both_files(monkeypatch, tmp_path) -> None:
    _patch(monkeypatch, {})

    result = cli.invoke(app, ["analyze", "--output", str(tmp_path / "report")])

    assert result.exit_code == 0, result.stdout
    md = tmp_path / "report.md"
    html = tmp_path / "report.html"
    assert md.exists() and html.exists()
    assert md.read_text(encoding="utf-8").startswith("# JMI Market Report")
    assert "<canvas" in html.read_text(encoding="utf-8")


def test_analyze_strips_extension_from_output(monkeypatch, tmp_path) -> None:
    _patch(monkeypatch, {})

    result = cli.invoke(app, ["analyze", "--output", str(tmp_path / "r.html")])

    assert result.exit_code == 0, result.stdout
    # `--output r.html` still yields r.md + r.html, not r.html.md / r.html.html
    assert (tmp_path / "r.md").exists()
    assert (tmp_path / "r.html").exists()
    assert not (tmp_path / "r.html.md").exists()


def test_analyze_skip_embed_forwarded(monkeypatch, tmp_path) -> None:
    recorder: dict = {}
    _patch(monkeypatch, recorder)

    result = cli.invoke(app, ["analyze", "--output", str(tmp_path / "r"), "--skip-embed"])

    assert result.exit_code == 0, result.stdout
    assert recorder["skip_embed"] is True


def test_analyze_default_does_not_skip_embed(monkeypatch, tmp_path) -> None:
    recorder: dict = {}
    _patch(monkeypatch, recorder)

    result = cli.invoke(app, ["analyze", "--output", str(tmp_path / "r")])

    assert result.exit_code == 0, result.stdout
    assert recorder["skip_embed"] is False


def test_analyze_exits_cleanly_on_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(db_base, "get_session", _fake_session)

    def failing_run_analysis(posting_repo, extract_repo, *, skip_embed):
        raise ValueError("no postings with description text to embed")

    monkeypatch.setattr(runner_mod, "run_analysis", failing_run_analysis)

    result = cli.invoke(app, ["analyze", "--output", str(tmp_path / "r")])

    # ValueError is caught and turned into a clean exit, not a crash.
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert not (tmp_path / "r.md").exists()
