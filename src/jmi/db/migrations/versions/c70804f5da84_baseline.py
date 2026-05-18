"""baseline

Revision ID: c70804f5da84
Revises:
Create Date: 2026-05-14 17:38:22.762406

Hand-written baseline migration. Mirrors the schema produced by
`Base.metadata.create_all()` against the Week 1 ORM in `src/jmi/db/models.py`.
For live dev databases that already have these tables, run
`alembic stamp c70804f5da84` to mark this revision as applied without
re-executing DDL. Fresh databases run `alembic upgrade head` to create
the schema from scratch.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c70804f5da84"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_postings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_job_id", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company_name", sa.String(length=256), nullable=False),
        sa.Column("location_raw", sa.String(length=256), nullable=True),
        sa.Column("description_html", sa.String(), nullable=False),
        sa.Column("description_text", sa.String(), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_job_id", name="uq_job_postings_source_job"),
    )
    op.create_index("ix_job_postings_company_name", "job_postings", ["company_name"])
    op.create_index("ix_job_postings_scraped_at", "job_postings", ["scraped_at"])
    op.create_index("ix_job_postings_source", "job_postings", ["source"])

    op.create_table(
        "job_extracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_posting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seniority", sa.String(length=32), nullable=True),
        sa.Column("tech_stack", sa.JSON(), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=8), nullable=True),
        sa.Column("remote_policy", sa.String(length=16), nullable=True),
        sa.Column("years_experience_min", sa.Integer(), nullable=True),
        sa.Column("employment_type", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("raw_llm_response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_extracts_extracted_at", "job_extracts", ["extracted_at"])
    op.create_index("ix_job_extracts_job_posting_id", "job_extracts", ["job_posting_id"])


def downgrade() -> None:
    op.drop_index("ix_job_extracts_job_posting_id", table_name="job_extracts")
    op.drop_index("ix_job_extracts_extracted_at", table_name="job_extracts")
    op.drop_table("job_extracts")
    op.drop_index("ix_job_postings_source", table_name="job_postings")
    op.drop_index("ix_job_postings_scraped_at", table_name="job_postings")
    op.drop_index("ix_job_postings_company_name", table_name="job_postings")
    op.drop_table("job_postings")
