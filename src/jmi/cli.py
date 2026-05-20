from datetime import date
from pathlib import Path

import typer

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
