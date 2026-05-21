"""Root pytest conftest.

The dummy ``DATABASE_URL`` survives for tests that construct ``Settings`` without
needing a live database (CLI ``--help`` exercises, pure-function tests). Tests
that need a real Postgres request the ``db_session`` fixture from
``tests.fixtures.postgres`` (loaded via ``pytest_plugins`` below); that fixture
overrides ``DATABASE_URL`` with the testcontainers URL and clears the cached
``Settings`` / ``Engine`` singletons.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")

pytest_plugins = ["tests.fixtures.postgres"]
