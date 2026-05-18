from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jmi.db.base import Base


class JobPostingORM(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("source", "source_job_id", name="uq_job_postings_source_job"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_job_id: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    location_raw: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description_html: Mapped[str | None] = mapped_column(nullable=True)
    description_text: Mapped[str | None] = mapped_column(nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    extracts: Mapped[list["JobExtractORM"]] = relationship(
        back_populates="posting",
        cascade="all, delete-orphan",
    )


class JobExtractORM(Base):
    __tablename__ = "job_extracts"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_posting_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tech_stack: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    salary_min: Mapped[int | None] = mapped_column(nullable=True)
    salary_max: Mapped[int | None] = mapped_column(nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    remote_policy: Mapped[str | None] = mapped_column(String(16), nullable=True)
    years_experience_min: Mapped[int | None] = mapped_column(nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_llm_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    extracted_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    posting: Mapped[JobPostingORM] = relationship(back_populates="extracts")
