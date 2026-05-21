from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from jmi.evaluation.benchmark import ScoredChunkAdapter
    from jmi.resume.schemas import CoverLetterDraft, ResumeBullet, TailoredResume
    from jmi.storage.tailored_resumes import TailoredResumeRow

from jmi.config import get_logging_settings, get_settings
from jmi.logging import configure_logging

app = typer.Typer(
    name="jmi",
    help="Job Market Intelligence - scrape, extract, analyze job postings.",
    no_args_is_help=True,
)

_SEED_OPTION = typer.Option(
    Path("docs/ground_truth/phase1_seed.json"),
    "--seed",
    help="Ground-truth seed JSON file.",
)

_OUTPUT_OPTION = typer.Option(
    None,
    "--output",
    "-o",
    help="Report path stem; writes {stem}.md and {stem}.html. Default: docs/market-report-{today}.",
)

_VAULT_PATH_OPTION = typer.Option(
    None,
    "--vault-path",
    help="Obsidian vault root. Defaults to the ACHIEVEMENTS_VAULT_PATH setting.",
)

_DB_UNREACHABLE_MSG = "Cannot connect to database — is `docker compose up` running?"

_RAG_SEED_OPTION = typer.Option(
    Path("docs/ground_truth/rag_retrieval_seed.json"),
    "--seed",
    help="Retrieval ground-truth seed JSON file.",
)

_RAG_BENCHMARK_OUT_OPTION = typer.Option(
    None,
    "--out",
    help=(
        "Write the rendered markdown report to this path. "
        "Default: experiments/pr32-benchmark/{pipeline}-rerank|norerank.md"
    ),
)


@app.callback()
def main() -> None:
    """Configure logging once per process using env-driven settings."""
    settings = get_logging_settings()
    configure_logging(json=settings.log_json, level=settings.log_level)


@app.command()
def scrape(
    source: str = typer.Option("huggingface", "--source", "-s", help="Job board source."),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max postings to scrape."),
) -> None:
    """Scrape job postings from a source into the database."""
    from sqlalchemy.exc import OperationalError

    from jmi.db.base import get_session
    from jmi.sources.huggingface import HuggingFaceScraper
    from jmi.storage.jobs import JobPostingRepository

    if source != "huggingface":
        typer.echo(f"Source '{source}' not implemented yet.", err=True)
        raise typer.Exit(1)

    scraper = HuggingFaceScraper()
    try:
        with get_session() as session:
            repo = JobPostingRepository(session)
            stats = scraper.run(repo, limit=limit)
    except OperationalError as exc:
        typer.echo(_DB_UNREACHABLE_MSG, err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"{stats.inserted} new, {stats.skipped} existing, {stats.invalid} invalid")


@app.command()
def extract(
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max postings to extract."),
    model: str = typer.Option("claude-opus-4-7", "--model", "-m", help="Anthropic model ID."),
) -> None:
    """Run LLM extraction on postings without an extract for the given model."""
    from sqlalchemy.exc import OperationalError

    from jmi.db.base import get_session
    from jmi.extractors import AnthropicExtractor
    from jmi.storage.jobs import JobExtractRepository, JobPostingRepository

    try:
        extractor = AnthropicExtractor(model=model)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    try:
        with get_session() as session:
            posting_repo = JobPostingRepository(session)
            extract_repo = JobExtractRepository(session)
            stats = extractor.run(posting_repo, extract_repo, limit=limit)
    except OperationalError as exc:
        typer.echo(_DB_UNREACHABLE_MSG, err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"{stats.inserted} extracted, {stats.skipped} already done, "
        f"{stats.invalid} invalid, {stats.refused} refused, "
        f"{stats.no_output} no_output, {stats.failed_api_calls} api_failures"
    )
    typer.echo(
        f"cache: {stats.cached_hits}/{stats.inserted} hits | "
        f"written {stats.total_cache_creation_tokens} / "
        f"read {stats.total_cache_read_tokens} tokens"
    )
    typer.echo(f"tokens: {stats.total_input_tokens} input, {stats.total_output_tokens} output")


@app.command()
def evaluate(
    seed: Path = _SEED_OPTION,
    source: str | None = typer.Option(
        None, "--source", "-s", help="Restrict evaluation to one source."
    ),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json."),
    show_unmatched: bool = typer.Option(
        False, "--show-unmatched", help="List labels that could not be evaluated."
    ),
) -> None:
    """Evaluate LLM extraction quality against ground-truth labels."""
    from jmi.db.base import get_session
    from jmi.evaluation.report import format_report, format_report_json
    from jmi.evaluation.runner import evaluate_all, load_seed
    from jmi.storage.jobs import JobExtractRepository, JobPostingRepository

    seed_entries = load_seed(seed)
    with get_session() as session:
        report = evaluate_all(
            seed_entries,
            JobPostingRepository(session),
            JobExtractRepository(session),
            source_filter=source,
        )

    if output == "json":
        typer.echo(format_report_json(report))
    else:
        typer.echo(format_report(report, show_unmatched=show_unmatched))


def _resolve_output_stem(output: Path | None, report_date: date) -> Path:
    """Resolve the --output argument to a path stem. A trailing .md/.html is
    stripped so `--output report.html` still yields report.md + report.html."""
    if output is None:
        return Path("docs") / f"market-report-{report_date.isoformat()}"
    text = str(output)
    for suffix in (".md", ".html"):
        if text.endswith(suffix):
            return Path(text[: -len(suffix)])
    return output


@app.command()
def analyze(
    output: Path | None = _OUTPUT_OPTION,
    skip_embed: bool = typer.Option(
        False,
        "--skip-embed",
        help="Reuse embeddings already stored in the DB instead of recomputing.",
    ),
) -> None:
    """Embed postings, cluster them, and write Markdown + HTML market reports."""
    from sqlalchemy.exc import OperationalError

    from jmi.analytics.report import generate_html_report, generate_markdown_report
    from jmi.analytics.runner import run_analysis
    from jmi.db.base import get_session
    from jmi.storage.jobs import JobExtractRepository, JobPostingRepository

    report_date = date.today()
    stem = _resolve_output_stem(output, report_date)

    try:
        with get_session() as session:
            bundle = run_analysis(
                JobPostingRepository(session),
                JobExtractRepository(session),
                skip_embed=skip_embed,
            )
    except (ValueError, OperationalError, RuntimeError, OSError) as exc:
        typer.echo(f"analyze failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    markdown = generate_markdown_report(bundle.cluster_result, bundle.jobs, report_date=report_date)
    html_report = generate_html_report(bundle.cluster_result, bundle.jobs, report_date=report_date)

    md_path = Path(f"{stem}.md")
    html_path = Path(f"{stem}.html")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_report, encoding="utf-8")

    result = bundle.cluster_result
    typer.echo(f"{len(bundle.jobs)} postings, k={result.k}, silhouette={result.silhouette:.2f}")
    typer.echo(f"wrote {md_path}")
    typer.echo(f"wrote {html_path}")


@app.command("ingest-achievements")
def ingest_achievements(
    vault_path: Path | None = _VAULT_PATH_OPTION,
) -> None:
    """Ingest achievement Markdown files from an Obsidian vault into the database."""
    from sqlalchemy.exc import OperationalError

    from jmi.db.base import get_session
    from jmi.sources.obsidian import ingest_vault
    from jmi.storage.achievements import AchievementRepository

    root = vault_path
    if root is None:
        configured = get_settings().achievements_vault_path
        if configured is None:
            typer.echo("No vault path: pass --vault-path or set ACHIEVEMENTS_VAULT_PATH.", err=True)
            raise typer.Exit(1)
        root = Path(configured)
    if not root.is_dir():
        typer.echo(f"Vault path is not a directory: {root}", err=True)
        raise typer.Exit(1)

    try:
        with get_session() as session:
            repo = AchievementRepository(session)
            stats = ingest_vault(repo, root)
    except OperationalError as exc:
        typer.echo(_DB_UNREACHABLE_MSG, err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"{stats.inserted} new, {stats.updated} updated, {stats.skipped} skipped, "
        f"{stats.invalid} invalid, {stats.rejected} rejected"
    )


_ACHIEVEMENT_ID_OPTION = typer.Option(
    None,
    "--achievement-id",
    help="UUID of a single achievement to (re-)embed. Repeat to embed several. "
    "Default: embed every achievement in the database.",
)


@app.command("rag-embed")
def rag_embed(
    achievement_id: list[str] | None = _ACHIEVEMENT_ID_OPTION,
) -> None:
    """Chunk, embed, and persist achievement_embeddings (PR-3.2, T3).

    Idempotent: every selected achievement's prior chunks are replaced.
    """
    from uuid import UUID

    from sqlalchemy.exc import OperationalError

    from jmi.db.base import get_session
    from jmi.rag.embedding import CustomEmbedder
    from jmi.rag.ingest import ingest_embeddings
    from jmi.storage.achievement_embeddings import AchievementEmbeddingRepository
    from jmi.storage.achievements import AchievementRepository

    try:
        ids: list[UUID] | None
        if achievement_id:
            try:
                ids = [UUID(a) for a in achievement_id]
            except ValueError as exc:
                typer.echo(f"invalid --achievement-id UUID: {exc}", err=True)
                raise typer.Exit(1) from exc
        else:
            ids = None
        embedder = CustomEmbedder()
        with get_session() as session:
            stats = ingest_embeddings(
                AchievementRepository(session),
                AchievementEmbeddingRepository(session),
                embedder,
                achievement_ids=ids,
            )
    except OperationalError as exc:
        typer.echo(_DB_UNREACHABLE_MSG, err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"{stats.achievements_processed} embedded, "
        f"{stats.achievements_skipped} skipped, "
        f"{stats.chunks_written} chunks written"
    )


@app.command("rag-query")
def rag_query(
    query: str = typer.Argument(..., help="Query text — typically a JD snippet or role."),
    k: int = typer.Option(5, "--k", help="Top-K chunks to return after the final stage."),
    no_rerank: bool = typer.Option(
        False, "--no-rerank", help="Skip the cross-encoder reranker — embedding order only."
    ),
) -> None:
    """Run the custom RAG pipeline and print the top-K chunks (PR-3.2, T6)."""
    from sqlalchemy.exc import OperationalError

    from jmi.db.base import get_session
    from jmi.rag.embedding import CustomEmbedder
    from jmi.rag.pipeline import RagPipeline
    from jmi.rag.reranking import CustomReranker
    from jmi.rag.retrieval import CustomRetriever

    if k <= 0:
        typer.echo("--k must be positive", err=True)
        raise typer.Exit(1)

    retriever = CustomRetriever(CustomEmbedder())
    reranker = None if no_rerank else CustomReranker()
    pipeline = RagPipeline(retriever, reranker)
    try:
        with get_session() as session:
            results = pipeline.retrieve_top_k(session, query, k=k)
    except OperationalError as exc:
        typer.echo(_DB_UNREACHABLE_MSG, err=True)
        raise typer.Exit(1) from exc

    stage = "rerank" if pipeline.has_reranker else "bi-encoder"
    typer.echo(f"top-{k} via {stage}:")
    for i, c in enumerate(results, start=1):
        first_line = c.chunk_text.splitlines()[0]
        typer.echo(f"  {i}. score={c.score:.4f} | {first_line}")


_GENERATE_TONE_OPTION = typer.Option(
    "conversational",
    "--tone",
    help="Cover letter tone: formal, conversational (default), or startup-casual.",
)
_GENERATE_JD_FILE_OPTION = typer.Option(
    None, "--jd-file", help="Path to JD text file (mutually exclusive with --jd-text)."
)
_GENERATE_OUTPUT_OPTION = typer.Option(
    None, "--output", help="Write markdown to this path (default: stdout)."
)
_GENERATE_JSON_OPTION = typer.Option(
    None, "--json", help="Write the full TailoredResume as JSON to this path."
)


@app.command("generate-resume")
def generate_resume(  # noqa: PLR0912, PLR0915 — orchestration is naturally branchy
    jd_file: Path | None = _GENERATE_JD_FILE_OPTION,
    jd_text: str | None = typer.Option(
        None, "--jd-text", help="JD text inline. Mutually exclusive with --jd-file."
    ),
    company: str | None = typer.Option(
        None, "--company", help="Override the company name parsed from the JD."
    ),
    output: Path | None = _GENERATE_OUTPUT_OPTION,
    json_out: Path | None = _GENERATE_JSON_OPTION,
    bullets_only: bool = typer.Option(False, "--bullets-only", help="Skip cover letter."),
    no_research: bool = typer.Option(
        False, "--no-research", help="Skip web_search; cover letter uses generic opener."
    ),
    research_depth: int = typer.Option(
        3, "--research-depth", min=1, max=5, help="web_search max_uses budget (1, 3, or 5)."
    ),
    refresh_research: bool = typer.Option(
        False, "--refresh-research", help="Bypass the per-company TTL cache."
    ),
    k: int = typer.Option(5, "--k", help="Top-K retrieved chunks after reranking."),
    bullets: int = typer.Option(
        6, "--bullets", min=5, max=10, help="Number of bullets to generate."
    ),
    tone: str = _GENERATE_TONE_OPTION,
    budget_usd: float | None = typer.Option(
        None, "--budget-usd", help="Abort before any paid call if estimate exceeds this."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print plan + cost estimate, exit without API calls."
    ),
    include_meta: bool = typer.Option(
        False, "--include-meta", help="Append generation metadata to the markdown output."
    ),
) -> None:
    """Generate a tailored resume + cover letter from a job description (PR-3.4)."""
    import hashlib
    import sys
    import time
    from datetime import UTC, datetime
    from typing import cast as _cast

    from sqlalchemy.exc import OperationalError

    from jmi.costs import estimate_generation_cost_usd
    from jmi.cover_letter.generator import CoverLetterGenerator
    from jmi.cover_letter.prompts import (
        PROMPT_VERSION as COVER_LETTER_PROMPT_VERSION,
    )
    from jmi.db.base import get_session
    from jmi.rag.embedding import MODEL_NAME as EMBED_MODEL_NAME
    from jmi.rag.embedding import CustomEmbedder
    from jmi.rag.pipeline import RagPipeline
    from jmi.rag.reranking import CustomReranker
    from jmi.rag.retrieval import CustomRetriever
    from jmi.research.company_agent import (
        RESEARCH_MODEL,
        SYNTHESIS_MODEL,
        CompanyResearchAgent,
    )
    from jmi.research.prompts import PROMPT_VERSION as RESEARCH_PROMPT_VERSION
    from jmi.resume.bullet_generator import (
        DEFAULT_MODEL as BULLET_MODEL,
    )
    from jmi.resume.bullet_generator import (
        StructuredBulletGenerator,
    )
    from jmi.resume.formatter import format_tailored_resume
    from jmi.resume.jd_parser import JD_PARSER_MODEL, JDTooShortError, parse_jd
    from jmi.resume.prompts import PROMPT_VERSION as BULLET_PROMPT_VERSION
    from jmi.resume.schemas import TailoredResume, Tone
    from jmi.storage.company_research_cache import CompanyResearchCacheRepository
    from jmi.storage.tailored_resumes import TailoredResumeRepository

    # Mutex: exactly one of --jd-file / --jd-text.
    if (jd_file is None) == (jd_text is None):
        typer.echo("Exactly one of --jd-file or --jd-text is required.", err=True)
        raise typer.Exit(code=2)

    if tone not in ("formal", "conversational", "startup-casual"):
        typer.echo(
            f"Unknown --tone {tone!r}; expected formal | conversational | startup-casual.",
            err=True,
        )
        raise typer.Exit(code=2)
    tone_typed: Tone = _cast(Tone, tone)

    raw_jd = jd_file.read_text(encoding="utf-8") if jd_file is not None else jd_text
    assert raw_jd is not None  # appease type-checker after the mutex above
    jd_hash = hashlib.sha256(raw_jd.strip().encode("utf-8")).hexdigest()

    estimated = estimate_generation_cost_usd(
        include_research=not no_research,
        include_cover_letter=not bullets_only,
    )

    if dry_run:
        typer.echo("─── jmi generate-resume --dry-run ───")
        typer.echo(f"JD characters: {len(raw_jd)}")
        typer.echo(f"JD hash: {jd_hash[:12]}…")
        typer.echo(f"Plan: jd_parse → retrieve(k={k})")
        if not no_research:
            typer.echo(f"      → research(depth={research_depth})")
        typer.echo(f"      → bullets({bullets})")
        if not bullets_only:
            typer.echo(f"      → cover_letter(tone={tone})")
        typer.echo(f"Estimated cost: ${estimated:.4f}")
        return

    if budget_usd is not None and estimated > budget_usd:
        typer.echo(
            f"Estimated cost ${estimated:.4f} exceeds --budget-usd ${budget_usd:.4f}. "
            "Aborting before any API call.",
            err=True,
        )
        raise typer.Exit(code=2)

    start_ns = time.perf_counter_ns()
    total_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    web_search_calls = 0

    try:
        # 1) Parse JD
        try:
            jd_result = parse_jd(raw_jd, override_company=company)
        except JDTooShortError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        jd = jd_result.jd
        total_cost += jd_result.cost_usd
        total_input_tokens += jd_result.input_tokens
        total_output_tokens += jd_result.output_tokens

        if jd.language == "pl":
            typer.echo(
                "Warning: Polish JD detected; English-only output in v1. "
                "Polish output is deferred to PR-3.5.",
                err=True,
            )

        # 2) Retrieve top-k chunks
        retriever = CustomRetriever(CustomEmbedder())
        reranker = CustomReranker()
        rag = RagPipeline(retriever, reranker=reranker)

        with get_session() as session:
            chunks = rag.retrieve_top_k(session, jd.raw_text, k=k)
            if not chunks:
                typer.echo(
                    "No retrievable chunks for this JD. "
                    "Run `jmi ingest-achievements` and `jmi rag-embed` first.",
                    err=True,
                )
                raise typer.Exit(code=2)

            # 3) Research (optional)
            research = None
            research_telemetry = None
            if not no_research:
                cache_repo = CompanyResearchCacheRepository(session)
                agent = CompanyResearchAgent(cache_repo=cache_repo)
                research_telemetry = agent.research_company(
                    jd.company_name,
                    jd.company_domain,
                    depth=research_depth,
                    use_cache=not refresh_research,
                )
                research = research_telemetry.research
                total_cost += research_telemetry.cost_usd
                total_input_tokens += research_telemetry.input_tokens
                total_output_tokens += research_telemetry.output_tokens
                web_search_calls += research_telemetry.web_search_calls

            # 4) Bullets
            bullet_gen = StructuredBulletGenerator()
            bullet_result = bullet_gen.generate(jd, chunks, bullet_count=bullets)
            total_cost += bullet_result.cost_usd
            total_input_tokens += bullet_result.input_tokens
            total_output_tokens += bullet_result.output_tokens

            # 5) Cover letter (optional)
            cover_letter_draft = None
            if not bullets_only:
                cl_gen = CoverLetterGenerator()
                cl_result = cl_gen.generate(jd, research, chunks, tone=tone_typed)
                cover_letter_draft = cl_result.draft
                total_cost += cl_result.cost_usd
                total_input_tokens += cl_result.input_tokens
                total_output_tokens += cl_result.output_tokens

            duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
            chunk_ids_used = _collect_chunk_ids(bullet_result.output.bullets, cover_letter_draft)
            model_versions = _build_model_versions(
                research=research is not None,
                cover_letter=cover_letter_draft is not None,
                embedder_name=EMBED_MODEL_NAME,
                bullet_model=BULLET_MODEL,
                jd_parser_model=JD_PARSER_MODEL,
                research_model=RESEARCH_MODEL,
                synthesis_model=SYNTHESIS_MODEL,
                bullet_prompt=BULLET_PROMPT_VERSION,
                cover_letter_prompt=COVER_LETTER_PROMPT_VERSION,
                research_prompt=RESEARCH_PROMPT_VERSION,
            )

            tr = TailoredResume(
                job_description=jd,
                bullets=bullet_result.output.bullets,
                uncovered_requirements=bullet_result.output.uncovered_requirements,
                cover_letter=cover_letter_draft,
                company_research=research,
                generated_at=datetime.now(UTC).replace(tzinfo=None),
                model_versions=model_versions,
                cost_usd=total_cost,
                total_tokens=total_input_tokens + total_output_tokens,
                web_search_calls=web_search_calls,
                generation_duration_ms=duration_ms,
                chunk_ids_used=chunk_ids_used,
                jd_hash=jd_hash,
            )

            # 6) Persist
            repo = TailoredResumeRepository(session)
            row = _tr_to_row(tr)
            saved_id = repo.save(row)
    except OperationalError as exc:
        typer.echo(_DB_UNREACHABLE_MSG, err=True)
        raise typer.Exit(1) from exc

    # 7) Render + write output
    markdown = format_tailored_resume(tr, include_meta=include_meta)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    else:
        typer.echo(markdown)

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(tr.model_dump_json(indent=2), encoding="utf-8")

    # 8) Cost block to stderr
    sys.stderr.write("\n─── jmi generate-resume ───\n")
    if research_telemetry is None:
        research_status = "no research"
    elif research_telemetry.cache_hit:
        research_status = "cache HIT"
    else:
        research_status = "cache MISS"
    sys.stderr.write(f"JD: {jd.company_name} → {jd.role_title} ({research_status})\n")
    sys.stderr.write(
        f"Retrieved {len(chunks)} chunks → bullets: "
        f"{len(bullet_result.output.bullets)} generated, "
        f"{bullet_result.refused_bullet_count} refused, "
        f"{len(bullet_result.output.uncovered_requirements)} uncovered JD requirements\n"
    )
    if cover_letter_draft is not None:
        sys.stderr.write(
            f"Cover letter: {cover_letter_draft.word_count} words, "
            f"company_specific_opener={cover_letter_draft.company_specific_opener}\n"
        )
    sys.stderr.write(f"Web search: {web_search_calls} calls\n")
    sys.stderr.write(f"Tokens: {total_input_tokens:,} in / {total_output_tokens:,} out\n")
    sys.stderr.write(f"Cost: ${total_cost:.4f}\n")
    sys.stderr.write(f"Duration: {duration_ms} ms\n")
    sys.stderr.write(f"Saved row: {saved_id}\n")


def _collect_chunk_ids(
    bullets: "list[ResumeBullet]",
    cover_letter: "CoverLetterDraft | None",
) -> list[str]:
    """Union of chunk_ids cited across bullets + cover letter paragraphs."""
    seen: list[str] = []
    for b in bullets:
        for cid in b.chunk_ids:
            if cid not in seen:
                seen.append(cid)
    if cover_letter is not None:
        for p in cover_letter.paragraphs:
            for cid in p.chunk_ids:
                if cid not in seen:
                    seen.append(cid)
    return seen


def _build_model_versions(
    *,
    research: bool,
    cover_letter: bool,
    embedder_name: str,
    bullet_model: str,
    jd_parser_model: str,
    research_model: str,
    synthesis_model: str,
    bullet_prompt: str,
    cover_letter_prompt: str,
    research_prompt: str,
) -> dict[str, str]:
    versions: dict[str, str] = {
        "embedder": embedder_name,
        "reranker": "BAAI/bge-reranker-base",
        "jd_parser_model": jd_parser_model,
        "bullet_model": bullet_model,
        "bullet_prompt": bullet_prompt,
    }
    if research:
        versions["research_model"] = research_model
        versions["synthesis_model"] = synthesis_model
        versions["research_prompt"] = research_prompt
    if cover_letter:
        versions["cover_letter_model"] = bullet_model  # same Opus 4.7
        versions["cover_letter_prompt"] = cover_letter_prompt
    return versions


def _tr_to_row(tr: "TailoredResume") -> "TailoredResumeRow":
    from uuid import uuid4

    from jmi.storage.tailored_resumes import TailoredResumeRow

    return TailoredResumeRow(
        id=uuid4(),
        created_at=tr.generated_at,
        jd_hash=tr.jd_hash,
        jd_text=tr.job_description.raw_text,
        company_name=tr.job_description.company_name,
        company_domain=tr.job_description.company_domain,
        role_title=tr.job_description.role_title,
        bullets_json=[b.model_dump(mode="json") for b in tr.bullets],
        cover_letter=(
            "\n\n".join(p.text for p in tr.cover_letter.paragraphs)
            if tr.cover_letter is not None
            else ""
        ),
        cover_letter_meta=(
            tr.cover_letter.model_dump(mode="json") if tr.cover_letter is not None else {}
        ),
        research_blob=(
            tr.company_research.model_dump(mode="json") if tr.company_research is not None else None
        ),
        chunk_ids_used=tr.chunk_ids_used,
        cost_usd=tr.cost_usd,
        total_tokens=tr.total_tokens,
        web_search_calls=tr.web_search_calls,
        generation_duration_ms=tr.generation_duration_ms,
        model_versions=tr.model_versions,
    )


@app.command("init-db")
def init_db() -> None:
    """Upgrade the database schema to the latest Alembic head."""
    from alembic import command
    from alembic.config import Config

    migrations_dir = Path(__file__).parent / "db" / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")
    typer.echo("Database upgraded to alembic head.")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Reload on code changes (dev only)."),
) -> None:
    """Start the FastAPI ingest endpoint server."""
    import uvicorn

    uvicorn.run(
        "jmi.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


@app.command("rag-benchmark")
def rag_benchmark(
    pipeline: str = typer.Option(
        "custom",
        "--pipeline",
        "-p",
        help="Which RAG pipeline to benchmark: 'custom' (worktree A) or 'langchain' (worktree B).",
    ),
    rerank: bool = typer.Option(
        True,
        "--rerank/--no-rerank",
        help="Enable the cross-encoder reranker. Default on.",
    ),
    k: int = typer.Option(5, "--k", help="top-K retrieved per query."),
    seed: Path = _RAG_SEED_OPTION,
    out: Path | None = _RAG_BENCHMARK_OUT_OPTION,
) -> None:
    """Score a RAG pipeline against the retrieval ground-truth seed.

    Requires the chosen pipeline's modules to be importable in the current
    worktree — `custom` needs `jmi.rag.pipeline` (worktree A's branch),
    `langchain` needs `jmi.rag_langchain.pipeline` (worktree B's branch).
    On worktree C alone the command exits with an explanatory error.
    """
    from sqlalchemy.exc import OperationalError

    from jmi.db.base import get_session
    from jmi.evaluation.benchmark import (
        benchmark_pipeline,
        format_benchmark_markdown,
        make_chunk_id_resolver,
    )
    from jmi.evaluation.retrieval_seed import load_seed

    if pipeline not in ("custom", "langchain"):
        typer.echo(f"unknown --pipeline {pipeline!r}; expected 'custom' or 'langchain'", err=True)
        raise typer.Exit(2)

    seed_file = load_seed(seed)

    try:
        with get_session() as session:
            resolver = make_chunk_id_resolver(session)
            adapter = _build_pipeline_adapter(pipeline, rerank, session, resolver)
            config = {"rerank": rerank, "pipeline": pipeline}
            result = benchmark_pipeline(
                adapter, seed_file, k=k, config=config, seed_file_path=str(seed)
            )
    except OperationalError as exc:
        typer.echo(f"{_DB_UNREACHABLE_MSG} ({exc})", err=True)
        raise typer.Exit(1) from exc

    markdown = format_benchmark_markdown(result)
    suffix = "rerank" if rerank else "norerank"
    out_path = out or Path(f"experiments/pr32-benchmark/{pipeline}-{suffix}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    typer.echo(
        f"recall@{k}={result.recall.mean:.3f} mrr={result.mrr.mean:.3f} "
        f"ndcg@{k}={result.ndcg.mean:.3f} -> wrote {out_path}"
    )


def _build_pipeline_adapter(
    pipeline_name: str,
    rerank: bool,
    session: object,  # SQLAlchemy Session, kept opaque to avoid the import here
    resolver: object,
) -> "ScoredChunkAdapter":
    """Import the requested pipeline lazily and wrap it in a `ScoredChunkAdapter`.

    Imports go through ``importlib.import_module`` so this module stays
    type-checkable on a branch that does not ship worktree A's or worktree
    B's pipeline packages — mypy never sees the symbol names. The adapter
    binds ``session`` for worktree A's session-injected interface; worktree
    B's PGVectorStore-backed pipeline owns its own connection and ignores
    it.
    """
    from collections.abc import Callable, Sequence
    from importlib import import_module

    from jmi.evaluation.benchmark import ScoredChunkAdapter, _ScoredChunkLike

    name = f"{pipeline_name}-{'rerank' if rerank else 'norerank'}"

    if pipeline_name == "custom":
        try:
            embedding_mod = import_module("jmi.rag.embedding")
            retrieval_mod = import_module("jmi.rag.retrieval")
            reranking_mod = import_module("jmi.rag.reranking")
            pipeline_mod = import_module("jmi.rag.pipeline")
        except ImportError as exc:
            typer.echo(
                "custom RAG modules not available on this branch — "
                "switch to worktree A (feat/phase3-pr3.2-A) and retry. "
                f"({exc})",
                err=True,
            )
            raise typer.Exit(3) from exc
        embedder = embedding_mod.CustomEmbedder()
        retriever = retrieval_mod.CustomRetriever(embedder)
        reranker = reranking_mod.CustomReranker() if rerank else None
        rag = pipeline_mod.RagPipeline(retriever, reranker=reranker)

        def retrieve_fn(query: str, k: int) -> Sequence[_ScoredChunkLike]:
            return list(rag.retrieve_top_k(session, query, k=k))

        rfn: Callable[[str, int], Sequence[_ScoredChunkLike]] = retrieve_fn
        rsv: Callable[..., str] = resolver  # type: ignore[assignment]
        return ScoredChunkAdapter(name, rfn, rsv)

    # langchain
    try:
        lc_pipeline_mod = import_module("jmi.rag_langchain.pipeline")
    except ImportError as exc:
        typer.echo(
            "langchain RAG modules not available on this branch — "
            "switch to worktree B (feat/phase3-pr3.2-B) and retry. "
            f"({exc})",
            err=True,
        )
        raise typer.Exit(3) from exc
    rag_lc = lc_pipeline_mod.RagPipeline()

    def retrieve_fn_lc(query: str, k: int) -> Sequence[_ScoredChunkLike]:
        return list(rag_lc.retrieve_top_k(query, k=k, rerank=rerank))

    rfn_lc: Callable[[str, int], Sequence[_ScoredChunkLike]] = retrieve_fn_lc
    rsv_lc: Callable[..., str] = resolver  # type: ignore[assignment]
    return ScoredChunkAdapter(name, rfn_lc, rsv_lc)
