from __future__ import annotations

import html
import json
from collections import Counter
from datetime import date

from pydantic import BaseModel, ConfigDict

from jmi.analytics.cluster import SILHOUETTE_WARN, ClusterResult
from jmi.analytics.schemas import JobView

CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1"
TOP_TECH_TERMS = 8
SAMPLE_TITLES = 3

_PIE_COLORS = ["#4571c4", "#e8743b", "#19a979", "#945ecf", "#cc3c43", "#7f8c8d"]


class ClusterSummary(BaseModel):
    """Per-cluster figures rendered by both report formats."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int
    size: int
    top_tech: list[tuple[str, int]]
    sample_titles: list[str]


class ReportData(BaseModel):
    """The single computed view both renderers consume — keeps Markdown and
    HTML output in lockstep (DRY)."""

    model_config = ConfigDict(extra="forbid")

    report_date: date
    total_postings: int
    per_source: dict[str, int]
    extract_coverage: int
    k: int
    silhouette: float
    silhouette_low: bool
    clusters: list[ClusterSummary]


def _build_report_data(
    cluster_result: ClusterResult, jobs: list[JobView], report_date: date
) -> ReportData:
    """Compute every figure the report shows. Shared by both renderers.

    Only `JobView` fields reach the report (posting_id, title, source,
    tech_stack) — company names and URLs are deliberately not carried here, so
    a committed Markdown report cannot leak them.
    """
    job_map = {j.posting_id: j for j in jobs}
    per_source = dict(sorted(Counter(j.source for j in jobs).items()))
    extract_coverage = sum(1 for j in jobs if j.tech_stack)

    summaries: list[ClusterSummary] = []
    for cluster in cluster_result.clusters:
        members = [job_map[pid] for pid in cluster.posting_ids if pid in job_map]
        term_counts: Counter[str] = Counter()
        for job in members:
            term_counts.update(job.tech_stack)
        # Deterministic order: count desc, then term asc — stable golden files.
        top_tech = sorted(term_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        summaries.append(
            ClusterSummary(
                cluster_id=cluster.cluster_id,
                size=len(members),
                top_tech=top_tech[:TOP_TECH_TERMS],
                sample_titles=sorted(j.title for j in members)[:SAMPLE_TITLES],
            )
        )

    return ReportData(
        report_date=report_date,
        total_postings=len(jobs),
        per_source=per_source,
        extract_coverage=extract_coverage,
        k=cluster_result.k,
        silhouette=cluster_result.silhouette,
        silhouette_low=cluster_result.silhouette < SILHOUETTE_WARN,
        clusters=summaries,
    )


def _postings_label(n: int) -> str:
    """'1 posting' / 'N postings' — for per-cluster headings."""
    return "1 posting" if n == 1 else f"{n} postings"


def _caveats(data: ReportData) -> list[str]:
    return [
        f"N = {data.total_postings} postings — a proof-of-concept sample, not "
        "market intelligence at scale.",
        f"k = {data.k} is fixed (not tuned) as a rough proxy for AI/ML role "
        "archetypes; clusters are forced even where structure is weak.",
        f"Tech-stack terms aggregate LLM extracts only — {data.extract_coverage} "
        f"of {data.total_postings} postings.",
        "Embeddings use sentence-transformers all-MiniLM-L6-v2 (local, no API "
        "cost); semantic quality is adequate for this PoC scale.",
        "Re-run at N > 50 for the first statistically meaningful clusters.",
    ]


def _render_markdown(data: ReportData) -> str:
    lines: list[str] = [
        f"# JMI Market Report — {data.report_date.isoformat()}",
        "",
        "## Coverage",
        "",
        f"{data.total_postings} postings clustered. Per-source breakdown:",
        "",
    ]
    lines += [f"- {source}: {count}" for source, count in data.per_source.items()]
    lines += [
        "",
        f"LLM extracts available for {data.extract_coverage} of "
        f"{data.total_postings} postings — the tech-stack term lists below "
        "cover only those.",
        "",
        "## Clusters",
        "",
        f"k = {data.k} (fixed). KMeans over MiniLM embeddings of posting "
        "title + description text.",
        "",
    ]
    for cluster in data.clusters:
        terms = (
            ", ".join(f"{term} ({count})" for term, count in cluster.top_tech)
            or "_no extract data_"
        )
        titles = "; ".join(cluster.sample_titles) or "_empty cluster_"
        lines += [
            f"### Cluster {cluster.cluster_id} — {_postings_label(cluster.size)}",
            "",
            f"- Top tech: {terms}",
            f"- Sample titles: {titles}",
            "",
        ]
    flag = (
        " — LOW (below the 0.20 warn threshold; clusters weakly separated, "
        "expected at small N)"
        if data.silhouette_low
        else ""
    )
    lines += [
        f"Silhouette: {data.silhouette:.2f}{flag}",
        "",
        "## Caveats",
        "",
    ]
    lines += [f"- {caveat}" for caveat in _caveats(data)]
    lines += [
        "",
        "See [docs/adr/0011-phase2-poc-choices.md](adr/0011-phase2-poc-choices.md) "
        "for the rationale behind these choices.",
        "",
    ]
    return "\n".join(lines)


_HTML_STYLE = """<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
h1 { border-bottom: 2px solid #4571c4; padding-bottom: .3rem; }
h2 { margin-top: 2rem; }
.charts { display: flex; gap: 2rem; flex-wrap: wrap; margin: 1.5rem 0; }
.chart-box { flex: 1 1 340px; }
article { background: #f5f6f8; border-radius: 6px; padding: .4rem 1rem; margin: .8rem 0; }
.silhouette { font-weight: 600; }
ul { line-height: 1.6; }
</style>"""

_CHART_INIT_JS = """new Chart(document.getElementById('sourcesChart'), {
  type: 'pie',
  data: { labels: sourceLabels,
          datasets: [{ data: sourceValues, backgroundColor: pieColors }] },
  options: { plugins: { title: { display: true, text: 'Postings by source' } } }
});
new Chart(document.getElementById('clustersChart'), {
  type: 'bar',
  data: { labels: clusterLabels,
          datasets: [{ label: 'Postings', data: clusterSizes,
                       backgroundColor: '#4571c4' }] },
  options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
             plugins: { title: { display: true, text: 'Cluster sizes' },
                        legend: { display: false } } }
});"""


def _render_html(data: ReportData) -> str:
    title = f"JMI Market Report — {data.report_date.isoformat()}"

    cluster_blocks: list[str] = []
    for cluster in data.clusters:
        terms = (
            ", ".join(
                f"{html.escape(term)} ({count})" for term, count in cluster.top_tech
            )
            or "<em>no extract data</em>"
        )
        titles = (
            "; ".join(html.escape(t) for t in cluster.sample_titles)
            or "<em>empty cluster</em>"
        )
        cluster_blocks.append(
            f"  <article>\n"
            f"    <h3>Cluster {cluster.cluster_id} — {_postings_label(cluster.size)}</h3>\n"
            f"    <p><strong>Top tech:</strong> {terms}</p>\n"
            f"    <p><strong>Sample titles:</strong> {titles}</p>\n"
            f"  </article>"
        )

    sources = "\n".join(
        f"  <li>{html.escape(source)}: {count}</li>"
        for source, count in data.per_source.items()
    )
    caveats = "\n".join(f"  <li>{html.escape(c)}</li>" for c in _caveats(data))
    flag = " — LOW" if data.silhouette_low else ""

    chart_script = (
        "<script>\n"
        f"const sourceLabels = {json.dumps(list(data.per_source.keys()))};\n"
        f"const sourceValues = {json.dumps(list(data.per_source.values()))};\n"
        f"const clusterLabels = {json.dumps([f'Cluster {c.cluster_id}' for c in data.clusters])};\n"
        f"const clusterSizes = {json.dumps([c.size for c in data.clusters])};\n"
        f"const pieColors = {json.dumps(_PIE_COLORS)};\n"
        f"{_CHART_INIT_JS}\n"
        "</script>"
    )

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html.escape(title)}</title>",
            f'<script src="{CHART_JS_CDN}"></script>',
            _HTML_STYLE,
            "</head>",
            "<body>",
            f"<h1>{html.escape(title)}</h1>",
            "<h2>Coverage</h2>",
            f"<p>{data.total_postings} postings clustered. LLM extracts available "
            f"for {data.extract_coverage} of {data.total_postings} — tech-stack "
            "lists cover only those.</p>",
            "<ul>",
            sources,
            "</ul>",
            '<div class="charts">',
            '  <div class="chart-box"><canvas id="sourcesChart"></canvas></div>',
            '  <div class="chart-box"><canvas id="clustersChart"></canvas></div>',
            "</div>",
            "<h2>Clusters</h2>",
            f"<p>k = {data.k} (fixed). KMeans over MiniLM embeddings of posting "
            "title + description text.</p>",
            *cluster_blocks,
            f'<p class="silhouette">Silhouette: {data.silhouette:.2f}{flag}</p>',
            "<h2>Caveats</h2>",
            "<ul>",
            caveats,
            "</ul>",
            chart_script,
            "</body>",
            "</html>",
            "",
        ]
    )


def generate_markdown_report(
    cluster_result: ClusterResult,
    jobs: list[JobView],
    *,
    report_date: date | None = None,
) -> str:
    """Render the market report as GitHub-friendly Markdown."""
    data = _build_report_data(cluster_result, jobs, report_date or date.today())
    return _render_markdown(data)


def generate_html_report(
    cluster_result: ClusterResult,
    jobs: list[JobView],
    *,
    report_date: date | None = None,
) -> str:
    """Render the market report as a single self-contained HTML file with
    Chart.js (loaded from CDN) bar + pie charts."""
    data = _build_report_data(cluster_result, jobs, report_date or date.today())
    return _render_html(data)
