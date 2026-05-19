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


class AchievementORM(Base):
    """Personal career achievement — content + metadata. A table separate from the
    job tables so personal data is purgeable independently (ADR-0014, S-3)."""

    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_achievements_slug"),
        UniqueConstraint("source_path", name="uq_achievements_source_path"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tech_stack: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    seniority_relevance: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    impact_metrics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    context: Mapped[str] = mapped_column(nullable=False)
    approach: Mapped[str] = mapped_column(nullable=False)
    impact: Mapped[str] = mapped_column(nullable=False)
    lessons: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    embeddings: Mapped[list["AchievementEmbeddingORM"]] = relationship(
        back_populates="achievement",
        cascade="all, delete-orphan",
    )


class AchievementEmbeddingORM(Base):
    """Chunk-level embedding of an achievement. Created empty by PR-3.1; the
    chunking + embedding pass that populates it lands in PR-3.2 (ADR-0014)."""

    __tablename__ = "achievement_embeddings"
    __table_args__ = (
        UniqueConstraint("achievement_id", "chunk_index", name="uq_achievement_embeddings_chunk"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    achievement_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    chunk_text: Mapped[str] = mapped_column(nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    achievement: Mapped[AchievementORM] = relationship(back_populates="embeddings")
