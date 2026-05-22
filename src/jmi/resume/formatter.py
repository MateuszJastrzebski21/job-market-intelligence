"""Markdown formatter for ``TailoredResume`` (PR-3.4).

Pure function: ``TailoredResume → str``. No I/O, no LLM calls. The
``--include-meta`` flag toggles an audit footer with chunk IDs, cost, and
model versions; useful for ADR-grade reproducibility but noisy for normal
operator review.

Output uses standard headings ("Selected Achievements", "Cover Letter") with
no emoji and no clever titles per Jobscan 2026 ATS guidance; the operator
can rewrite headings downstream if their target ATS prefers different ones.
"""

from __future__ import annotations

from jmi.resume.schemas import (
    CoverLetterDraft,
    JobDescription,
    ResumeBullet,
    TailoredResume,
)


def format_tailored_resume(tr: TailoredResume, *, include_meta: bool = False) -> str:
    """Render ``tr`` as a markdown document.

    Layout:
        # <role title> — <company>

        ## Selected Achievements
        - <bullet 1>
        - <bullet 2>
        ...

        ## Cover Letter
        <opener>

        <body...>

        <closer>

        --- (only if include_meta)
        ## Generation Metadata
        - …
    """
    sections: list[str] = []

    sections.append(_render_header(tr.job_description))
    sections.append(_render_bullets(tr.bullets, tr.uncovered_requirements))

    if tr.cover_letter is not None:
        sections.append(_render_cover_letter(tr.cover_letter, tr.job_description))

    if include_meta:
        sections.append(_render_meta(tr))

    return "\n\n".join(sections).rstrip() + "\n"


def _render_header(jd: JobDescription) -> str:
    return f"# {jd.role_title} — {jd.company_name}"


def _render_bullets(bullets: list[ResumeBullet], uncovered: list[str]) -> str:
    lines: list[str] = ["## Selected Achievements", ""]
    for b in bullets:
        lines.append(f"- {b.text}")

    if uncovered:
        lines.extend(
            [
                "",
                "### Requirements not covered by current achievements",
                "",
            ]
        )
        for r in uncovered:
            lines.append(f"- {r}")

    return "\n".join(lines)


def _render_cover_letter(cl: CoverLetterDraft, jd: JobDescription) -> str:
    lines: list[str] = ["## Cover Letter", ""]
    for para in cl.paragraphs:
        lines.append(para.text)
        lines.append("")
    if not cl.company_specific_opener:
        lines.append(
            f"_Note: generated with research_confidence={cl.research_confidence}; "
            "opener is role-generic rather than company-specific._"
        )
    return "\n".join(lines).rstrip()


def _render_meta(tr: TailoredResume) -> str:
    lines: list[str] = [
        "---",
        "",
        "## Generation Metadata",
        "",
        f"- Generated at: {tr.generated_at.isoformat()}",
        f"- Cost: ${tr.cost_usd:.4f}",
        f"- Total tokens: {tr.total_tokens:,}",
        f"- Web search calls: {tr.web_search_calls}",
        f"- Duration: {tr.generation_duration_ms} ms",
        f"- Chunks cited: {', '.join(tr.chunk_ids_used) or '(none)'}",
        f"- JD hash: {tr.jd_hash[:12]}…",
        "- Models:",
    ]
    for k, v in sorted(tr.model_versions.items()):
        lines.append(f"  - {k}: {v}")
    if tr.company_research is not None:
        lines.append(
            f"- Research: confidence={tr.company_research.confidence}, "
            f"news={len(tr.company_research.recent_news)}, "
            f"tech={len(tr.company_research.tech_stack_signals)}"
        )
    return "\n".join(lines)
