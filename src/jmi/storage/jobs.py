from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from jmi.db.models import JobExtractORM, JobPostingORM
from jmi.models.job import JobExtract, JobPosting


class JobPostingRepository:
    """Domain ↔ persistence boundary for JobPosting. Callers see Pydantic,
    SQLAlchemy stays behind the session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, item: JobPosting) -> JobPosting:
        orm = _posting_to_orm(item)
        self._session.add(orm)
        self._session.flush()
        return _posting_to_domain(orm)

    def get(self, id: UUID) -> JobPosting | None:
        orm = self._session.get(JobPostingORM, id)
        return _posting_to_domain(orm) if orm else None

    def get_by_source(self, source: str, source_job_id: str) -> JobPosting | None:
        stmt = select(JobPostingORM).where(
            JobPostingORM.source == source,
            JobPostingORM.source_job_id == source_job_id,
        )
        orm = self._session.execute(stmt).scalar_one_or_none()
        return _posting_to_domain(orm) if orm else None

    def list(self, limit: int = 100, offset: int = 0) -> list[JobPosting]:
        stmt = (
            select(JobPostingORM)
            .order_by(JobPostingORM.scraped_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_posting_to_domain(o) for o in self._session.execute(stmt).scalars()]


class JobExtractRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, item: JobExtract) -> JobExtract:
        orm = _extract_to_orm(item)
        self._session.add(orm)
        self._session.flush()
        return _extract_to_domain(orm)

    def get(self, id: UUID) -> JobExtract | None:
        orm = self._session.get(JobExtractORM, id)
        return _extract_to_domain(orm) if orm else None

    def list(self, limit: int = 100, offset: int = 0) -> list[JobExtract]:
        stmt = (
            select(JobExtractORM)
            .order_by(JobExtractORM.extracted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_extract_to_domain(o) for o in self._session.execute(stmt).scalars()]

    def list_by_posting(self, posting_id: UUID) -> list[JobExtract]:
        stmt = (
            select(JobExtractORM)
            .where(JobExtractORM.job_posting_id == posting_id)
            .order_by(JobExtractORM.extracted_at.desc())
        )
        return [_extract_to_domain(o) for o in self._session.execute(stmt).scalars()]


def _posting_to_orm(p: JobPosting) -> JobPostingORM:
    return JobPostingORM(
        id=p.id,
        source=p.source,
        source_job_id=p.source_job_id,
        url=str(p.url),
        title=p.title,
        company_name=p.company_name,
        location_raw=p.location_raw,
        description_html=p.description_html,
        description_text=p.description_text,
        posted_at=p.posted_at,
        scraped_at=p.scraped_at,
        raw_payload=p.raw_payload,
    )


def _posting_to_domain(o: JobPostingORM) -> JobPosting:
    return JobPosting(
        id=o.id,
        source=o.source,  # type: ignore[arg-type]
        source_job_id=o.source_job_id,
        url=o.url,  # type: ignore[arg-type]
        title=o.title,
        company_name=o.company_name,
        location_raw=o.location_raw,
        description_html=o.description_html,
        description_text=o.description_text,
        posted_at=o.posted_at,
        scraped_at=o.scraped_at,
        raw_payload=o.raw_payload,
    )


def _extract_to_orm(e: JobExtract) -> JobExtractORM:
    return JobExtractORM(
        id=e.id,
        job_posting_id=e.job_posting_id,
        seniority=e.seniority,
        tech_stack=list(e.tech_stack),
        salary_min=e.salary_min,
        salary_max=e.salary_max,
        salary_currency=e.salary_currency,
        remote_policy=e.remote_policy,
        years_experience_min=e.years_experience_min,
        employment_type=e.employment_type,
        model_name=e.model_name,
        raw_llm_response=e.raw_llm_response,
        extracted_at=e.extracted_at,
    )


def _extract_to_domain(o: JobExtractORM) -> JobExtract:
    return JobExtract(
        id=o.id,
        job_posting_id=o.job_posting_id,
        seniority=o.seniority,  # type: ignore[arg-type]
        tech_stack=list(o.tech_stack),
        salary_min=o.salary_min,
        salary_max=o.salary_max,
        salary_currency=o.salary_currency,
        remote_policy=o.remote_policy,  # type: ignore[arg-type]
        years_experience_min=o.years_experience_min,
        employment_type=o.employment_type,  # type: ignore[arg-type]
        model_name=o.model_name,
        raw_llm_response=o.raw_llm_response,
        extracted_at=o.extracted_at,
    )
