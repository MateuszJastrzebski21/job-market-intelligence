"""nullable description columns

Revision ID: 1347689491ea
Revises: c70804f5da84
Create Date: 2026-05-14 17:39:18.450310

Make `description_html` and `description_text` nullable on `job_postings`.
Required by the HITL ingest flow (PR3+): listing-page rows are created with
NULL descriptions, then filled in by the background detail fetcher.
Downgrade reverses the change but will fail if any rows hold NULL values.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1347689491ea"
down_revision: Union[str, Sequence[str], None] = "c70804f5da84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "job_postings",
        "description_html",
        existing_type=sa.String(),
        nullable=True,
    )
    op.alter_column(
        "job_postings",
        "description_text",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "job_postings",
        "description_text",
        existing_type=sa.String(),
        nullable=False,
    )
    op.alter_column(
        "job_postings",
        "description_html",
        existing_type=sa.String(),
        nullable=False,
    )
