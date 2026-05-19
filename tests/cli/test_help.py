"""`jmi <cmd> --help` must work without DATABASE_URL set (#58).

The Typer callback used to build the DB-coupled Settings for every invocation,
so subcommand `--help` crashed with a ValidationError when DATABASE_URL was
unset. Logging config now comes from LoggingSettings, which has no DB field.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from jmi.cli import app
from jmi.config import get_logging_settings, get_settings

cli = CliRunner()


@pytest.fixture
def no_database_url(monkeypatch) -> Iterator[None]:
    """Unset DATABASE_URL and clear settings caches so a stray Settings()
    construction on the --help path would actually raise."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    get_logging_settings.cache_clear()
    yield
    get_settings.cache_clear()
    get_logging_settings.cache_clear()


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["scrape", "--help"],
        ["extract", "--help"],
        ["evaluate", "--help"],
        ["analyze", "--help"],
        ["init-db", "--help"],
        ["serve", "--help"],
    ],
)
@pytest.mark.usefixtures("no_database_url")
def test_help_without_database_url(argv: list[str]) -> None:
    result = cli.invoke(app, argv)
    assert result.exit_code == 0, result.output
