from __future__ import annotations

import typer

from jmi.config import get_settings
from jmi.logging import configure_logging

app = typer.Typer(
    name="jmi",
    help="Job Market Intelligence - scrape, extract, analyze job postings.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Configure logging once per process using env-driven settings."""
    settings = get_settings()
    configure_logging(json=settings.log_json, level=settings.log_level)


@app.command()
def scrape(
    source: str = typer.Option("huggingface", "--source", "-s", help="Job board source."),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max postings to scrape."),
) -> None:
    """Scrape job postings from a source into the database."""
    from jmi.db.base import get_session
    from jmi.sources.huggingface import HuggingFaceScraper
    from jmi.storage.jobs import JobPostingRepository

    if source != "huggingface":
        typer.echo(f"Source '{source}' not implemented yet.", err=True)
        raise typer.Exit(1)

    scraper = HuggingFaceScraper()
    with get_session() as session:
        repo = JobPostingRepository(session)
        stats = scraper.run(repo, limit=limit)
    typer.echo(
        f"{stats.inserted} new, {stats.skipped} existing, {stats.invalid} invalid"
    )


@app.command()
def extract(
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max postings to extract."),
    model: str = typer.Option(
        "claude-opus-4-7", "--model", "-m", help="Anthropic model ID."
    ),
) -> None:
    """Run LLM extraction on postings without an extract for the given model."""
    from jmi.db.base import get_session
    from jmi.extractors import AnthropicExtractor
    from jmi.storage.jobs import JobExtractRepository, JobPostingRepository

    extractor = AnthropicExtractor(model=model)
    with get_session() as session:
        posting_repo = JobPostingRepository(session)
        extract_repo = JobExtractRepository(session)
        stats = extractor.run(posting_repo, extract_repo, limit=limit)

    typer.echo(
        f"{stats.inserted} extracted, {stats.skipped} already done, "
        f"{stats.invalid} invalid, {stats.failed_api_calls} api_failures"
    )
    typer.echo(
        f"cache: {stats.cached_hits}/{stats.inserted} hits | "
        f"written {stats.total_cache_creation_tokens} / "
        f"read {stats.total_cache_read_tokens} tokens"
    )
    typer.echo(
        f"tokens: {stats.total_input_tokens} input, {stats.total_output_tokens} output"
    )


@app.command("init-db")
def init_db() -> None:
    """Upgrade the database schema to the latest Alembic head."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    migrations_dir = Path(__file__).parent / "db" / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")
    typer.echo("Database upgraded to alembic head.")
