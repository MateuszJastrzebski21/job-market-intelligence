"""create achievement tables

Revision ID: 523e5acbff52
Revises: d0a61d5836d4
Create Date: 2026-05-19 16:56:42.365498

Create the Phase 3 personal-achievement schema (ADR-0014): `achievements`
(content + metadata) and `achievement_embeddings` (chunk-level pgvector rows,
created empty here — PR-3.2's chunking + embedding pass populates them). Both
tables are kept separate from the job-posting tables so personal data is
purgeable independently (design-constraints S-3): this migration's
`downgrade()` is that documented purge path — it drops every personal vector
and source row and touches no job data. The `CREATE EXTENSION` guard is
idempotent — the extension is normally already present from `docker/init.sql`
and the earlier embedding migration; this keeps the migration runnable against
a database created without that init script.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "523e5acbff52"
down_revision: str | Sequence[str] | None = "d0a61d5836d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("tech_stack", sa.JSON(), nullable=False),
        sa.Column("seniority_relevance", sa.JSON(), nullable=False),
        sa.Column("impact_metrics", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("context", sa.String(), nullable=False),
        sa.Column("approach", sa.String(), nullable=False),
        sa.Column("impact", sa.String(), nullable=False),
        sa.Column("lessons", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_achievements_slug"),
        sa.UniqueConstraint("source_path", name="uq_achievements_source_path"),
    )
    op.create_index("ix_achievements_created_at", "achievements", ["created_at"])

    op.create_table(
        "achievement_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("achievement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.String(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "achievement_id", "chunk_index", name="uq_achievement_embeddings_chunk"
        ),
    )
    op.create_index(
        "ix_achievement_embeddings_achievement_id",
        "achievement_embeddings",
        ["achievement_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_achievement_embeddings_achievement_id", table_name="achievement_embeddings")
    op.drop_table("achievement_embeddings")
    op.drop_index("ix_achievements_created_at", table_name="achievements")
    op.drop_table("achievements")
