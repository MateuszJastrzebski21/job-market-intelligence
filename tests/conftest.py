"""Root pytest conftest.

Shared fixtures will land here in Week 2 alongside integration tests
(testcontainers-driven Postgres + repository fixtures).
"""
import os

# Settings now requires DATABASE_URL — there is no default credential fallback
# (#26). Tests never touch a real database, but constructing Settings (e.g. via
# the `jmi` CLI callback exercised by CLI tests) still validates the field, so
# provide a dummy value suite-wide. setdefault keeps any real value intact.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test"
)
