"""Tests for the `jmi ingest-achievements` CLI command.

Kept DB-free by monkeypatching get_session and ingest_vault — the same pattern
as tests/cli/test_analyze.py.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace

from typer.testing import CliRunner

import jmi.cli as cli_module
import jmi.db.base as db_base
import jmi.sources.obsidian as obsidian
from jmi.cli import app
from jmi.sources.obsidian import IngestStats

cli = CliRunner()


@contextmanager
def _fake_session() -> Iterator[object]:
    yield object()


def _fake_ingest_vault(_repo: object, _path: object) -> IngestStats:
    return IngestStats(inserted=3, updated=1, skipped=2, invalid=0, rejected=0)


def test_ingest_achievements_reports_stats(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(db_base, "get_session", _fake_session)
    monkeypatch.setattr(obsidian, "ingest_vault", _fake_ingest_vault)

    result = cli.invoke(app, ["ingest-achievements", "--vault-path", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    assert "3 new" in result.stdout
    assert "1 updated" in result.stdout
    assert "2 skipped" in result.stdout


def test_ingest_achievements_rejects_a_missing_directory(tmp_path) -> None:
    missing = tmp_path / "does-not-exist"

    result = cli.invoke(app, ["ingest-achievements", "--vault-path", str(missing)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_ingest_achievements_requires_a_vault_path(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_module, "get_settings", lambda: SimpleNamespace(achievements_vault_path=None)
    )

    result = cli.invoke(app, ["ingest-achievements"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
