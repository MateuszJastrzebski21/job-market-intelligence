"""Tests for the `jmi evaluate` CLI command.

Kept DB-free by monkeypatching get_session, load_seed, and evaluate_all —
the runner's logic is covered by test_runner.py.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from typer.testing import CliRunner

import jmi.db.base as db_base
import jmi.evaluation.runner as runner_mod
from jmi.cli import app
from jmi.evaluation.report import EvaluationReport
from jmi.evaluation.runner import evaluate_all

cli = CliRunner()


@contextmanager
def _fake_session() -> Iterator[object]:
    yield object()


def _build_report(
    posting_repo,
    extract_repo,
    make_posting: Callable[..., object],
    make_extract: Callable[..., object],
    make_entry: Callable[..., object],
) -> EvaluationReport:
    """A real report: one matched entry plus one unmatched (id-only) entry."""
    posting = make_posting(source_job_id="JOB-001")
    posting_repo.add(posting)
    extract_repo.add(
        make_extract(job_posting_id=posting.id, seniority="senior", remote_policy="remote")
    )
    matched = make_entry(
        source_job_id="JOB-001",
        expected={"seniority": "senior", "remote_policy": "remote"},
    )
    id_only = make_entry(id="hf-IDONLY1234", source_job_id=None)
    return evaluate_all([matched, id_only], posting_repo, extract_repo)


def _patch(monkeypatch, report: EvaluationReport, recorder: dict) -> None:
    monkeypatch.setattr(db_base, "get_session", _fake_session)
    monkeypatch.setattr(runner_mod, "load_seed", lambda path: [])

    def fake_evaluate_all(seed, posting_repo, extract_repo, source_filter=None):
        recorder["source_filter"] = source_filter
        return report

    monkeypatch.setattr(runner_mod, "evaluate_all", fake_evaluate_all)


def test_evaluate_text_output(
    monkeypatch, posting_repo, extract_repo, make_posting, make_extract, make_entry
) -> None:
    report = _build_report(posting_repo, extract_repo, make_posting, make_extract, make_entry)
    _patch(monkeypatch, report, {})

    result = cli.invoke(app, ["evaluate"])

    assert result.exit_code == 0
    assert "EVALUATION REPORT" in result.stdout
    assert "Per-field accuracy" in result.stdout
    assert "Per-source breakdown" in result.stdout


def test_evaluate_source_filter_forwarded(
    monkeypatch, posting_repo, extract_repo, make_posting, make_extract, make_entry
) -> None:
    report = _build_report(posting_repo, extract_repo, make_posting, make_extract, make_entry)
    recorder: dict = {}
    _patch(monkeypatch, report, recorder)

    result = cli.invoke(app, ["evaluate", "--source", "jjit"])

    assert result.exit_code == 0
    assert recorder["source_filter"] == "jjit"


def test_evaluate_json_output_is_valid(
    monkeypatch, posting_repo, extract_repo, make_posting, make_extract, make_entry
) -> None:
    report = _build_report(posting_repo, extract_repo, make_posting, make_extract, make_entry)
    _patch(monkeypatch, report, {})

    result = cli.invoke(app, ["evaluate", "--output", "json"])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "ok"
    assert parsed["total_labels"] == 2


def test_evaluate_show_unmatched_lists_id_only(
    monkeypatch, posting_repo, extract_repo, make_posting, make_extract, make_entry
) -> None:
    report = _build_report(posting_repo, extract_repo, make_posting, make_extract, make_entry)
    _patch(monkeypatch, report, {})

    default_run = cli.invoke(app, ["evaluate"])
    assert "Unmatched labels" not in default_run.stdout

    shown = cli.invoke(app, ["evaluate", "--show-unmatched"])
    assert shown.exit_code == 0
    assert "Unmatched labels" in shown.stdout
    assert "reason=id_only" in shown.stdout
