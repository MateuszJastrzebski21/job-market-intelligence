"""Tests for graceful CLI error handling — missing API key and DB down (#25).

Same DB-free pattern as tests/cli/test_analyze.py: the CLI is invoked through
CliRunner with get_session / the extractor monkeypatched to fail.
"""

from __future__ import annotations

from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

import jmi.db.base as db_base
import jmi.extractors as extractors_mod
from jmi.cli import app

cli = CliRunner()


def _raise_operational_error(*_args: object, **_kwargs: object) -> object:
    raise OperationalError("SELECT 1", None, Exception("connection refused"))


class _NoKeyExtractor:
    """Stand-in for AnthropicExtractor whose construction fails like a missing key."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env "
            "(copy from .env.example) before running `jmi extract`."
        )


class _OkExtractor:
    """Stand-in extractor whose construction succeeds (the DB is the failure)."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass


def test_extract_missing_api_key_exits_cleanly(monkeypatch) -> None:
    """A missing ANTHROPIC_API_KEY surfaces a clean exit(1), not a traceback."""
    monkeypatch.setattr(extractors_mod, "AnthropicExtractor", _NoKeyExtractor)

    result = cli.invoke(app, ["extract"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_extract_db_unreachable_exits_cleanly(monkeypatch) -> None:
    """`jmi extract` against a down database exits(1) with a friendly message."""
    monkeypatch.setattr(extractors_mod, "AnthropicExtractor", _OkExtractor)
    monkeypatch.setattr(db_base, "get_session", _raise_operational_error)

    result = cli.invoke(app, ["extract"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_scrape_db_unreachable_exits_cleanly(monkeypatch) -> None:
    """`jmi scrape` against a down database exits(1) with a friendly message."""
    monkeypatch.setattr(db_base, "get_session", _raise_operational_error)

    result = cli.invoke(app, ["scrape"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
