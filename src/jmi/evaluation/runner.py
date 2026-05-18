"""Evaluation orchestration: load labels, match extracts, aggregate metrics.

The functions here take repository objects (not a Session) so they can be
unit-tested against in-memory fakes — see ADR-0010 and tests/evaluation/.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Protocol
from uuid import UUID

import structlog

from jmi.evaluation.metrics import (
    exact_match,
    jaccard_similarity,
    numeric_match_or_both_null,
    salary_match,
)
from jmi.evaluation.report import (
    BOOLEAN_FIELDS,
    TECH_STACK_THRESHOLD,
    EvaluationReport,
    EvaluationResult,
    FieldAccuracy,
    FieldResult,
    SalaryStats,
    SourceBreakdown,
    TechStackStats,
    UnmatchedDetail,
    unmatched_hint,
)
from jmi.evaluation.schemas import GroundTruthEntry, parse_seed
from jmi.models.job import JobExtract, JobPosting

log = structlog.get_logger(__name__)


class PostingFinder(Protocol):
    """The slice of JobPostingRepository the runner needs."""

    def get_by_source(self, source: str, source_job_id: str) -> JobPosting | None: ...


class ExtractLister(Protocol):
    """The slice of JobExtractRepository the runner needs."""

    def list_by_posting(self, posting_id: UUID) -> list[JobExtract]: ...


def load_seed(path: Path) -> list[GroundTruthEntry]:
    """Read and validate a ground-truth seed file (a top-level JSON array)."""
    return parse_seed(path.read_bytes())


def get_extract_for_label(
    entry: GroundTruthEntry,
    posting_repo: PostingFinder,
    extract_repo: ExtractLister,
) -> tuple[JobExtract | None, str | None]:
    """Find the extract to evaluate for a seed entry.

    Returns ``(extract, None)`` on success, or ``(None, reason)`` where reason
    is ``id_only`` (no source_job_id), ``no_posting`` (nothing in the DB), or
    ``no_extract`` (posting exists but was never extracted). When a posting
    has several extracts, the most recent one is returned.
    """
    if entry.source_job_id is None:
        return None, "id_only"
    posting = posting_repo.get_by_source(entry.source, entry.source_job_id)
    if posting is None:
        return None, "no_posting"
    extracts = extract_repo.list_by_posting(posting.id)
    if not extracts:
        return None, "no_extract"
    return extracts[0], None  # list_by_posting is ordered extracted_at DESC


def evaluate_entry(
    entry: GroundTruthEntry,
    extract: JobExtract | None,
    missing_reason: str | None,
) -> EvaluationResult:
    """Compare one seed entry's expected values against its extract."""
    if extract is None:
        return EvaluationResult(
            entry_id=entry.id,
            source=entry.source,
            has_extract=False,
            missing_reason=missing_reason,
            extract_id=None,
            model_name=None,
        )

    expected = entry.expected
    fields: list[FieldResult] = []

    for name in ("seniority", "remote_policy", "employment_type"):
        exp = getattr(expected, name)
        act = getattr(extract, name)
        match = exact_match(act, exp)
        fields.append(FieldResult(name, exp, act, 1.0 if match else 0.0, match))

    yexp, yact = expected.years_experience_min, extract.years_experience_min
    ymatch = numeric_match_or_both_null(yact, yexp)
    fields.append(FieldResult("years_experience_min", yexp, yact, 1.0 if ymatch else 0.0, ymatch))

    ts_score = jaccard_similarity(extract.tech_stack, expected.tech_stack)
    fields.append(
        FieldResult(
            "tech_stack",
            expected.tech_stack,
            extract.tech_stack,
            ts_score,
            ts_score >= TECH_STACK_THRESHOLD,
        )
    )

    sal_match = salary_match(
        extract.salary_min,
        extract.salary_max,
        expected.salary_min,
        expected.salary_max,
    )
    fields.append(
        FieldResult(
            "salary",
            (expected.salary_min, expected.salary_max),
            (extract.salary_min, extract.salary_max),
            1.0 if sal_match else 0.0,
            sal_match,
        )
    )

    cur_match = exact_match(extract.salary_currency, expected.salary_currency)
    fields.append(
        FieldResult(
            "salary_currency",
            expected.salary_currency,
            extract.salary_currency,
            1.0 if cur_match else 0.0,
            cur_match,
        )
    )

    return EvaluationResult(
        entry_id=entry.id,
        source=entry.source,
        has_extract=True,
        missing_reason=None,
        extract_id=extract.id,
        model_name=extract.model_name,
        fields=fields,
    )


def _boolean_accuracy(
    pairs: list[tuple[GroundTruthEntry, JobExtract]],
) -> dict[str, FieldAccuracy]:
    out: dict[str, FieldAccuracy] = {}
    for name in BOOLEAN_FIELDS:
        matches = 0
        for entry, extract in pairs:
            exp = getattr(entry.expected, name)
            act = getattr(extract, name)
            if name == "years_experience_min":
                ok = numeric_match_or_both_null(act, exp)
            else:
                ok = exact_match(act, exp)
            if ok:
                matches += 1
        evaluated = len(pairs)
        out[name] = FieldAccuracy(
            field=name,
            evaluated=evaluated,
            matches=matches,
            accuracy=(matches / evaluated) if evaluated else None,
        )
    return out


def _tech_stack_stats(
    pairs: list[tuple[GroundTruthEntry, JobExtract]],
) -> TechStackStats:
    scores = [
        jaccard_similarity(extract.tech_stack, entry.expected.tech_stack)
        for entry, extract in pairs
    ]
    if not scores:
        return TechStackStats(
            evaluated=0,
            jaccard_avg=None,
            jaccard_min=None,
            jaccard_max=None,
            jaccard_median=None,
            threshold=TECH_STACK_THRESHOLD,
            pass_count=0,
            pass_rate=None,
        )
    passed = sum(1 for s in scores if s >= TECH_STACK_THRESHOLD)
    return TechStackStats(
        evaluated=len(scores),
        jaccard_avg=sum(scores) / len(scores),
        jaccard_min=min(scores),
        jaccard_max=max(scores),
        jaccard_median=statistics.median(scores),
        threshold=TECH_STACK_THRESHOLD,
        pass_count=passed,
        pass_rate=passed / len(scores),
    )


def _salary_stats(
    pairs: list[tuple[GroundTruthEntry, JobExtract]],
) -> SalaryStats:
    min_label = min_captured = 0
    max_label = max_captured = 0
    currency_total = currency_match = 0
    correct_currency = wrong_currency = 0

    for entry, extract in pairs:
        exp = entry.expected
        if exp.salary_min is not None:
            min_label += 1
            if extract.salary_min is not None:
                min_captured += 1
        if exp.salary_max is not None:
            max_label += 1
            if extract.salary_max is not None:
                max_captured += 1
        if exp.salary_currency is not None:
            currency_total += 1
            if extract.salary_currency == exp.salary_currency:
                currency_match += 1

        label_has_salary = exp.salary_min is not None or exp.salary_max is not None
        extract_has_salary = extract.salary_min is not None or extract.salary_max is not None
        if label_has_salary and extract_has_salary:
            if extract.salary_currency == exp.salary_currency:
                correct_currency += 1
            else:
                wrong_currency += 1

    return SalaryStats(
        min_label_count=min_label,
        min_captured_count=min_captured,
        min_recall=(min_captured / min_label) if min_label else None,
        max_label_count=max_label,
        max_captured_count=max_captured,
        max_recall=(max_captured / max_label) if max_label else None,
        currency_total=currency_total,
        currency_match_count=currency_match,
        currency_match_rate=(currency_match / currency_total if currency_total else None),
        salary_with_correct_currency=correct_currency,
        salary_with_wrong_currency=wrong_currency,
    )


def _source_breakdown(
    source: str,
    seed: list[GroundTruthEntry],
    pairs: list[tuple[GroundTruthEntry, JobExtract]],
) -> SourceBreakdown:
    total = sum(1 for e in seed if e.source == source)
    src_pairs = [(e, x) for e, x in pairs if e.source == source]
    boolean = _boolean_accuracy(src_pairs)
    ts = _tech_stack_stats(src_pairs)
    sal = _salary_stats(src_pairs)
    return SourceBreakdown(
        source=source,
        total_labels=total,
        evaluable=len(src_pairs),
        unmatched=total - len(src_pairs),
        boolean_accuracy={k: v.accuracy for k, v in boolean.items()},
        tech_stack_jaccard_avg=ts.jaccard_avg,
        salary_min_recall=sal.min_recall,
    )


def evaluate_all(
    seed: list[GroundTruthEntry],
    posting_repo: PostingFinder,
    extract_repo: ExtractLister,
    source_filter: str | None = None,
) -> EvaluationReport:
    """Evaluate every seed entry and aggregate the results into a report."""
    if source_filter is not None:
        seed = [e for e in seed if e.source == source_filter]

    if not seed:
        return EvaluationReport(
            status="no_labels",
            source_filter=source_filter,
            total_labels=0,
            with_extract=0,
            without_extract=0,
            boolean_metrics=_boolean_accuracy([]),
            tech_stack_metrics=_tech_stack_stats([]),
            salary_metrics=_salary_stats([]),
            per_source={},
        )

    results: list[EvaluationResult] = []
    pairs: list[tuple[GroundTruthEntry, JobExtract]] = []
    unmatched: list[UnmatchedDetail] = []

    for entry in seed:
        extract, reason = get_extract_for_label(entry, posting_repo, extract_repo)
        results.append(evaluate_entry(entry, extract, reason))
        if extract is not None:
            pairs.append((entry, extract))
        else:
            unmatched.append(
                UnmatchedDetail(
                    entry_id=entry.id,
                    source=entry.source,
                    reason=reason or "unknown",
                    hint=unmatched_hint(reason or ""),
                )
            )
            if reason == "id_only":
                log.warning(
                    "evaluation.label_unmatched",
                    entry_id=entry.id,
                    reason=reason,
                )

    sources = sorted({e.source for e in seed})
    return EvaluationReport(
        status="ok",
        source_filter=source_filter,
        total_labels=len(seed),
        with_extract=len(pairs),
        without_extract=len(unmatched),
        boolean_metrics=_boolean_accuracy(pairs),
        tech_stack_metrics=_tech_stack_stats(pairs),
        salary_metrics=_salary_stats(pairs),
        per_source={s: _source_breakdown(s, seed, pairs) for s in sources},
        results=results,
        unmatched_details=unmatched,
    )
