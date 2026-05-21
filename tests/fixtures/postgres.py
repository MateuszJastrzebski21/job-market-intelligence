"""Session-scoped Postgres container + per-test transaction-rollback session.

The ``pgvector/pgvector:pg15`` image is the same one used by ``docker-compose.yml``
for local dev, so tests run against the production-equivalent database. The
container spins up once per pytest session (~5s startup) and per-test isolation
comes from a transaction rolled back at teardown rather than truncating tables.

Loaded into the test suite via ``pytest_plugins`` in ``tests/conftest.py``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start ``pgvector/pgvector:pg15`` once per pytest session.

    Driver ``psycopg`` (psycopg3) matches the runtime pin in ``pyproject.toml``.
    """
    container = PostgresContainer(image="pgvector/pgvector:pg15", driver="psycopg")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_engine(postgres_container: PostgresContainer) -> Iterator[Engine]:
    """Engine bound to the container with the vector extension + alembic head applied.

    Exposes ``DATABASE_URL`` so anything that touches ``get_settings()`` after this
    fixture fires (e.g. alembic env.py) sees the test database. Cached singletons
    in ``jmi.config`` and ``jmi.db.base`` are cleared so prior dummy values do not
    stick across the boundary.
    """
    url = postgres_container.get_connection_url()
    os.environ["DATABASE_URL"] = url

    from jmi.config import get_settings
    from jmi.db.base import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()

    engine = create_engine(url, future=True, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """Function-scoped session inside an outer transaction that rolls back at teardown.

    The Session sees its own writes within the test; nothing escapes to the next
    test. Repos that accept ``session: Session`` plug straight in — there is no
    need to monkeypatch ``get_session()``.
    """
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
