"""add embedding to job postings

Revision ID: d0a61d5836d4
Revises: 1347689491ea
Create Date: 2026-05-18 10:55:28.673870

Add a nullable `embedding` column (pgvector `vector(384)`) to `job_postings`,
holding the sentence-transformers all-MiniLM-L6-v2 embedding of the posting's
title + description text. Nullable because embeddings are produced by a
separate analytics pass (`jmi analyze`, ADR-0011), not at ingest time. The
`CREATE EXTENSION` guard is idempotent — on the dev/CI databases the extension
is already installed by `docker/init.sql`; this keeps the migration runnable
against a database created without that init script.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "d0a61d5836d4"
down_revision: str | Sequence[str] | None = "1347689491ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "job_postings",
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_postings", "embedding")
