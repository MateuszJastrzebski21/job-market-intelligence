"""Integration tests for the evaluation runner against in-memory fakes."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from jmi.evaluation.runner import evaluate_all, load_seed
from jmi.evaluation.schemas import GroundTruthEntry
from jmi.models.job import JobExtract, JobPosting


def test_load_seed_parses_array(sample_seed_file) -> None:
    entries = load_seed(sample_seed_file)
    assert len(entries) == 2
    assert entries[0].source_job_id == "JOB-AAA"
    assert entries[1].source_job_id is None  # id-only few-shot entry


def test_empty_seed_returns_no_labels_status(posting_repo, extract_repo) -> None:
    report = evaluate_all([], posting_repo, extract_repo)
    assert report.status == "no_labels"
    assert report.total_labels == 0
    assert report.with_extract == 0
    assert report.without_extract == 0


def test_id_only_entry_counted_as_unmatched(
    posting_repo, extract_repo, make_entry: Callable[..., GroundTruthEntry]
) -> None:
    entry = make_entry(source_job_id=None)
    report = evaluate_all([entry], posting_repo, extract_repo)
    assert report.status == "ok"
    assert report.with_extract == 0
    assert report.without_extract == 1
    assert report.unmatched_details[0].reason == "id_only"


def test_posting_without_extract_is_no_extract(
    posting_repo,
    extract_repo,
    make_posting: Callable[..., JobPosting],
    make_entry: Callable[..., GroundTruthEntry],
) -> None:
    posting_repo.add(make_posting(source_job_id="JOB-001"))
    entry = make_entry(source_job_id="JOB-001")
    report = evaluate_all([entry], posting_repo, extract_repo)
    assert report.with_extract == 0
    assert report.unmatched_details[0].reason == "no_extract"


def test_happy_path_aggregates_metrics(
    posting_repo,
    extract_repo,
    make_posting: Callable[..., JobPosting],
    make_extract: Callable[..., JobExtract],
    make_entry: Callable[..., GroundTruthEntry],
) -> None:
    posting = make_posting(source_job_id="JOB-001")
    posting_repo.add(posting)
    extract_repo.add(
        make_extract(
            job_posting_id=posting.id,
            seniority="senior",
            tech_stack=["Python", "PyTorch"],
            remote_policy="remote",
        )
    )
    entry = make_entry(
        source_job_id="JOB-001",
        expected={
            "seniority": "senior",
            "tech_stack": ["Python", "PyTorch"],
            "remote_policy": "remote",
        },
    )
    report = evaluate_all([entry], posting_repo, extract_repo)

    assert report.with_extract == 1
    assert report.boolean_metrics["seniority"].accuracy == 1.0
    assert report.boolean_metrics["remote_policy"].accuracy == 1.0
    assert report.tech_stack_metrics.jaccard_avg == 1.0
    assert "huggingface" in report.per_source


def test_latest_extract_wins(
    posting_repo,
    extract_repo,
    make_posting: Callable[..., JobPosting],
    make_extract: Callable[..., JobExtract],
    make_entry: Callable[..., GroundTruthEntry],
    older_then_newer: tuple[datetime, datetime],
) -> None:
    older, newer = older_then_newer
    posting = make_posting(source_job_id="JOB-001")
    posting_repo.add(posting)
    extract_repo.add(
        make_extract(job_posting_id=posting.id, seniority="junior", extracted_at=older)
    )
    extract_repo.add(
        make_extract(job_posting_id=posting.id, seniority="senior", extracted_at=newer)
    )
    entry = make_entry(source_job_id="JOB-001", expected={"seniority": "senior"})
    report = evaluate_all([entry], posting_repo, extract_repo)

    assert report.boolean_metrics["seniority"].accuracy == 1.0  # newer extract used


def test_salary_recall_and_source_filter(
    posting_repo,
    extract_repo,
    make_posting: Callable[..., JobPosting],
    make_extract: Callable[..., JobExtract],
    make_entry: Callable[..., GroundTruthEntry],
) -> None:
    posting = make_posting(source_job_id="JOB-001")
    posting_repo.add(posting)
    # label has a salary; extract failed to capture it -> recall miss
    extract_repo.add(make_extract(job_posting_id=posting.id, salary_min=None))
    entry = make_entry(
        source_job_id="JOB-001",
        expected={"salary_min": 120000, "salary_currency": "USD"},
    )
    report = evaluate_all([entry], posting_repo, extract_repo)

    assert report.salary_metrics.min_label_count == 1
    assert report.salary_metrics.min_captured_count == 0
    assert report.salary_metrics.min_recall == 0.0

    # source filter excludes all entries -> no_labels
    filtered = evaluate_all([entry], posting_repo, extract_repo, source_filter="jjit")
    assert filtered.status == "no_labels"
