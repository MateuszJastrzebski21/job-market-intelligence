"""add tailored_resumes and company_research_cache (PR-3.4)

Revision ID: ba8e241d6cd8
Revises: 523e5acbff52
Create Date: 2026-05-21 12:00:00.000000

Add two PR-3.4 tables:

- `tailored_resumes` — one row per `jmi generate-resume` invocation. Holds
  the JD text, the bullets/cover-letter output, the company research blob,
  the chunk-ids cited, and per-generation cost/duration telemetry. Permanent
  retention by operator decision (dossier §10 Q2 + Q7); `jmi vault purge`
  is deferred to PR-3.5.
- `company_research_cache` — TTL-bounded cache of `CompanyResearch`
  payloads keyed by SHA256(normalised company_name + domain). Default TTL
  7 days (set application-side in the repo, not the schema). Saves the
  ~$0.078 research-call cost on repeat applications to the same company.

`chunk_ids_used` is `text[]` of stringified UUIDs (the `achievement_embeddings.id`
PK), with a GIN index for "which generations cited this chunk?" analytics.
Deliberately NOT a foreign key — re-chunking the achievement vault would
otherwise cascade-migrate every past row (ADR-0014 separability + ADR-0016
forthcoming).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ba8e241d6cd8"
down_revision: str | Sequence[str] | None = "523e5acbff52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tailored_resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("jd_hash", sa.CHAR(64), nullable=False),
        sa.Column("jd_text", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("company_domain", sa.String(), nullable=True),
        sa.Column("role_title", sa.String(), nullable=True),
        sa.Column(
            "bullets_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("cover_letter", sa.String(), nullable=False),
        sa.Column(
            "cover_letter_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "research_blob",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "chunk_ids_used",
            postgresql.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "web_search_calls",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("generation_duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "model_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tailored_resumes_company_created_at",
        "tailored_resumes",
        ["company_name", sa.text("created_at DESC")],
    )
    op.create_index("ix_tailored_resumes_jd_hash", "tailored_resumes", ["jd_hash"])
    op.create_index(
        "ix_tailored_resumes_chunk_ids_used",
        "tailored_resumes",
        ["chunk_ids_used"],
        postgresql_using="gin",
    )

    op.create_table(
        "company_research_cache",
        sa.Column("key", sa.CHAR(64), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("company_domain", sa.String(), nullable=True),
        sa.Column(
            "research_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        "ix_company_research_cache_fetched_at",
        "company_research_cache",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_research_cache_fetched_at",
        table_name="company_research_cache",
    )
    op.drop_table("company_research_cache")
    op.drop_index("ix_tailored_resumes_chunk_ids_used", table_name="tailored_resumes")
    op.drop_index("ix_tailored_resumes_jd_hash", table_name="tailored_resumes")
    op.drop_index(
        "ix_tailored_resumes_company_created_at",
        table_name="tailored_resumes",
    )
    op.drop_table("tailored_resumes")
