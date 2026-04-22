from __future__ import annotations

import typer

app = typer.Typer(
    name="jmi",
    help="Job Market Intelligence — scrape, extract, analyze job postings.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Top-level callback. Logging setup wired in Step 4."""


@app.command()
def scrape(
    source: str = typer.Option("wellfound", "--source", "-s", help="Job board source."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max postings to scrape."),
) -> None:
    """Scrape job postings from a source (weekend)."""
    raise NotImplementedError("scrape: implemented weekend with Wellfound scraper")


@app.command()
def extract(
    limit: int = typer.Option(50, "--limit", "-n", help="Max postings to extract."),
) -> None:
    """Run LLM extraction on un-extracted postings (weekend)."""
    raise NotImplementedError("extract: implemented weekend with Anthropic SDK")


@app.command("init-db")
def init_db() -> None:
    """Create tables (temporary until Alembic lands in Week 2)."""
    raise NotImplementedError("init-db: implemented in Step 3 once ORM exists")
