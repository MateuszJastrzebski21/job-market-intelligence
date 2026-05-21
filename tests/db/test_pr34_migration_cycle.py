"""Alembic upgrade/downgrade cycle test for PR-3.4's migration (ba8e241d6cd8).

Verifies the migration is reversible: downgrade by one drops the new tables
without touching prior schema, and re-upgrading restores them. Restores head
at the end so downstream session-scoped tests keep working.
"""

from __future__ import annotations

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, inspect


def test_migration_downgrade_and_reupgrade(migrated_engine: Engine) -> None:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option(
        "sqlalchemy.url",
        migrated_engine.url.render_as_string(hide_password=False),
    )

    command.downgrade(cfg, "-1")
    with migrated_engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
    assert "tailored_resumes" not in tables, "downgrade should drop tailored_resumes"
    assert "company_research_cache" not in tables, "downgrade should drop company_research_cache"
    assert "achievements" in tables, "downgrade -1 must not touch prior migrations"
    assert "achievement_embeddings" in tables

    command.upgrade(cfg, "head")
    with migrated_engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
    assert "tailored_resumes" in tables
    assert "company_research_cache" in tables
