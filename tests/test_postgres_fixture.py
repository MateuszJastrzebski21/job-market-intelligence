"""Smoke tests for the testcontainers Postgres fixtures (PR-3.4 prep)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def test_db_session_opens_and_queries(db_session: Session) -> None:
    """The session is wired and can round-trip a trivial query."""
    result = db_session.execute(text("SELECT 1 AS one")).scalar_one()
    assert result == 1


def test_vector_extension_present(db_session: Session) -> None:
    """``CREATE EXTENSION vector`` ran before migrations — pgvector is queryable."""
    extensions = db_session.execute(text("SELECT extname FROM pg_extension")).scalars().all()
    assert "vector" in extensions


def test_migrations_applied_to_head(db_session: Session) -> None:
    """``alembic upgrade head`` ran during fixture setup; expected tables exist."""
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    assert {
        "job_postings",
        "job_extracts",
        "achievements",
        "achievement_embeddings",
    }.issubset(tables)


def test_transaction_rollback_isolates_tests_part_a(db_session: Session) -> None:
    """Write a marker row inside the per-test transaction."""
    db_session.execute(text("CREATE TEMP TABLE IF NOT EXISTS _isolation_probe (v INT)"))
    db_session.execute(text("INSERT INTO _isolation_probe VALUES (42)"))
    db_session.flush()
    count = db_session.execute(text("SELECT COUNT(*) FROM _isolation_probe")).scalar_one()
    assert count == 1


def test_transaction_rollback_isolates_tests_part_b(db_session: Session) -> None:
    """Part A's write rolled back at teardown — this test sees an empty / absent table."""
    table_exists = db_session.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = '_isolation_probe')")
    ).scalar_one()
    assert table_exists is False
