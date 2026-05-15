"""Result dataclasses and report renderers for extraction-quality evaluation.

The runner produces an :class:`EvaluationReport`; the renderers here turn it
into either a human-readable text report or a JSON document.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from uuid import UUID

# Categorical / numeric fields scored by a boolean match. Salary and
# tech_stack get their own report sections.
BOOLEAN_FIELDS = ("seniority", "remote_policy", "employment_type", "years_experience_min")

TECH_STACK_THRESHOLD = 0.8


@dataclass
class FieldResult:
    """One field's comparison for one seed entry."""

    field: str
    expected: object
    actual: object
    score: float  # 1.0/0.0 for boolean fields, Jaccard for tech_stack
    is_match: bool


@dataclass
class EvaluationResult:
    """The outcome for a single seed entry."""

    entry_id: str
    source: str
    has_extract: bool
    missing_reason: str | None  # None | "id_only" | "no_posting" | "no_extract"
    extract_id: UUID | None
    model_name: str | None
    fields: list[FieldResult] = field(default_factory=list)


@dataclass
class FieldAccuracy:
    """Aggregate exact-match accuracy for one boolean field."""

    field: str
    evaluated: int
    matches: int
    accuracy: float | None  # matches / evaluated, or None when evaluated == 0


@dataclass
class TechStackStats:
    """Aggregate Jaccard statistics for tech_stack across evaluable entries."""

    evaluated: int
    jaccard_avg: float | None
    jaccard_min: float | None
    jaccard_max: float | None
    jaccard_median: float | None
    threshold: float
    pass_count: int
    pass_rate: float | None  # entries with Jaccard >= threshold


@dataclass
class SalaryStats:
    """Salary recall: did the extractor capture salaries the label has?"""

    min_label_count: int
    min_captured_count: int
    min_recall: float | None
    max_label_count: int
    max_captured_count: int
    max_recall: float | None
    currency_total: int
    currency_match_count: int
    currency_match_rate: float | None
    # Of entries whose label has a salary and whose extract captured one:
    salary_with_correct_currency: int
    salary_with_wrong_currency: int


@dataclass
class SourceBreakdown:
    """Compact metric view restricted to a single source."""

    source: str
    total_labels: int
    evaluable: int
    unmatched: int
    boolean_accuracy: dict[str, float | None]
    tech_stack_jaccard_avg: float | None
    salary_min_recall: float | None


@dataclass
class UnmatchedDetail:
    """A seed entry that could not be scored, with a remediation hint."""

    entry_id: str
    source: str
    reason: str
    hint: str


@dataclass
class EvaluationReport:
    """The full evaluation result, ready to render."""

    status: str  # "ok" | "no_labels"
    source_filter: str | None
    total_labels: int
    with_extract: int
    without_extract: int
    boolean_metrics: dict[str, FieldAccuracy]
    tech_stack_metrics: TechStackStats
    salary_metrics: SalaryStats
    per_source: dict[str, SourceBreakdown]
    results: list[EvaluationResult] = field(default_factory=list)
    unmatched_details: list[UnmatchedDetail] = field(default_factory=list)


_UNMATCHED_HINTS = {
    "id_only": "add source_job_id to the label to enable eval",
    "no_posting": "no posting in DB for this source_job_id — run `jmi scrape`",
    "no_extract": "posting exists but has no extract — run `jmi extract`",
}


def unmatched_hint(reason: str) -> str:
    """Human-readable remediation hint for an unmatched reason code."""
    return _UNMATCHED_HINTS.get(reason, "unknown reason")


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.0f}%"


def format_report(report: EvaluationReport, *, show_unmatched: bool = False) -> str:
    """Render a human-readable text report."""
    lines: list[str] = []
    lines.append("EVALUATION REPORT")
    lines.append("=" * 17)
    lines.append("")
    lines.append(f"Source filter: {report.source_filter or 'all'}")

    if report.status == "no_labels":
        lines.append("")
        lines.append("No ground-truth labels found — nothing to evaluate.")
        return "\n".join(lines)

    lines.append(f"Total labels: {report.total_labels}")
    lines.append(f"  - With extract: {report.with_extract}")
    lines.append(
        f"  - Without extract: {report.without_extract} "
        f"(unmatched or no extract yet)"
    )

    if report.with_extract == 0:
        lines.append("")
        lines.append(
            "No evaluable labels (all labels are unmatched or lack an extract). "
            "Run with --show-unmatched for details."
        )
    else:
        lines.append("")
        lines.append("Per-field accuracy (exact match where applicable):")
        for name in BOOLEAN_FIELDS:
            fa = report.boolean_metrics[name]
            lines.append(
                f"  {name:<22}: {_pct(fa.accuracy)} "
                f"({fa.matches}/{fa.evaluated})"
            )

        ts = report.tech_stack_metrics
        lines.append("")
        lines.append("Per-field similarity (continuous metric):")
        if ts.jaccard_avg is None:
            lines.append("  tech_stack (Jaccard): N/A")
        else:
            lines.append(f"  tech_stack (Jaccard avg): {ts.jaccard_avg:.2f}")
            lines.append(
                f"    - Range: {ts.jaccard_min:.2f} - {ts.jaccard_max:.2f}"
            )
            lines.append(f"    - Median: {ts.jaccard_median:.2f}")
            lines.append(
                f"    - >={ts.threshold:.0%} threshold passed: "
                f"{ts.pass_count}/{ts.evaluated} ({_pct(ts.pass_rate)})"
            )

        sal = report.salary_metrics
        lines.append("")
        lines.append("Per-field salary recall (critical metric):")
        lines.append(
            f"  salary_min present in label: {sal.min_label_count}/"
            f"{report.with_extract}"
        )
        warn_min = " <!>" if (sal.min_recall is not None and sal.min_recall < 0.5) else ""
        lines.append(
            f"  salary_min captured in extract: {sal.min_captured_count}/"
            f"{sal.min_label_count} ({_pct(sal.min_recall)} recall){warn_min}"
        )
        lines.append(
            f"  salary_max present in label: {sal.max_label_count}/"
            f"{report.with_extract}"
        )
        warn_max = " <!>" if (sal.max_recall is not None and sal.max_recall < 0.5) else ""
        lines.append(
            f"  salary_max captured in extract: {sal.max_captured_count}/"
            f"{sal.max_label_count} ({_pct(sal.max_recall)} recall){warn_max}"
        )
        captured_total = (
            sal.salary_with_correct_currency + sal.salary_with_wrong_currency
        )
        lines.append(
            f"  salary captured WITH correct currency: "
            f"{sal.salary_with_correct_currency}/{captured_total}"
        )
        lines.append(
            f"  salary_currency match: {sal.currency_match_count}/"
            f"{sal.currency_total} ({_pct(sal.currency_match_rate)})"
        )

        lines.append("")
        lines.append("Per-source breakdown:")
        for sb in report.per_source.values():
            lines.append(
                f"  {sb.source:<11}: {sb.total_labels} labels, "
                f"{sb.evaluable} evaluable ({sb.unmatched} unmatched)"
            )
            sen = sb.boolean_accuracy.get("seniority")
            lines.append(
                f"    seniority: {_pct(sen)}, "
                f"tech_stack jaccard: "
                f"{'N/A' if sb.tech_stack_jaccard_avg is None else f'{sb.tech_stack_jaccard_avg:.2f}'}, "
                f"salary_min recall: {_pct(sb.salary_min_recall)}"
            )

    if show_unmatched and report.unmatched_details:
        lines.append("")
        lines.append("Unmatched labels (debugging):")
        for u in report.unmatched_details:
            lines.append(
                f'  - id="{u.entry_id}" reason={u.reason} ({u.hint})'
            )

    return "\n".join(lines)


def format_report_json(report: EvaluationReport) -> str:
    """Render the report as a JSON document. UUIDs are stringified."""
    return json.dumps(
        dataclasses.asdict(report),
        indent=2,
        default=lambda o: str(o) if isinstance(o, UUID) else None,
    )
