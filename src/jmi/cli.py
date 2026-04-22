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
    limit: int = typer.Option(50, "--limit", "-n", help="Max postings to extract."),
) -> None:
    """Run LLM extraction on un-extracted postings (weekend)."""
    raise NotImplementedError("extract: implemented weekend with Anthropic SDK")


@app.command("init-db")
def init_db() -> None:
    """Create tables (temporary until Alembic lands in Week 2)."""
    from jmi.db import models  # noqa: F401  — register ORM models on Base.metadata
    from jmi.db.base import Base, engine

    Base.metadata.create_all(bind=engine)
    typer.echo("Tables created.")
