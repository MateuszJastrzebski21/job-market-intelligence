from __future__ import annotations

from datetime import UTC, datetime

import jmi
from jmi.models.job import JobExtract, JobPosting


def test_version_is_set() -> None:
    assert jmi.__version__


def test_job_posting_validates_happy_path() -> None:
    posting = JobPosting(
        source="wellfound",
        source_job_id="w-123",
        url="https://wellfound.com/jobs/123",
        title="Senior Python Engineer",
        company_name="Acme",
        description_html="<p>hi</p>",
        description_text="hi",
        scraped_at=datetime.now(tz=UTC),
    )
    assert posting.source == "wellfound"
    assert posting.id is not None


def test_job_extract_requires_model_name() -> None:
    extract = JobExtract(
        job_posting_id=JobPosting(
            source="wellfound",
            source_job_id="w-1",
            url="https://wellfound.com/jobs/1",
            title="Eng",
            company_name="Acme",
            description_html="<p>x</p>",
            description_text="x",
            scraped_at=datetime.now(tz=UTC),
        ).id,
        model_name="claude-opus-4-7",
        extracted_at=datetime.now(tz=UTC),
    )
    assert extract.tech_stack == []
    assert extract.model_name == "claude-opus-4-7"
