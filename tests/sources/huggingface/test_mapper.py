from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from jmi.sources.huggingface import mapper

FIXTURE = Path(__file__).parent / "fixtures" / "workable_response.json"


@pytest.fixture
def workable_response() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def scraped_at() -> datetime:
    return datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)


def test_maps_all_required_fields(workable_response: dict, scraped_at: datetime) -> None:
    job_dict = workable_response["jobs"][0]
    posting = mapper.to_posting(job_dict, company_name="Hugging Face", scraped_at=scraped_at)

    assert posting.source == "huggingface"
    assert posting.source_job_id == job_dict["shortcode"]
    assert posting.title == job_dict["title"]
    assert posting.company_name == "Hugging Face"
    assert str(posting.url) == job_dict["url"]
    assert posting.scraped_at == scraped_at
    assert posting.raw_payload == job_dict


def test_description_html_preserved_and_text_extracted(
    workable_response: dict, scraped_at: datetime
) -> None:
    job_dict = workable_response["jobs"][0]
    posting = mapper.to_posting(job_dict, company_name="Hugging Face", scraped_at=scraped_at)

    assert "<" in posting.description_html
    assert "<" not in posting.description_text
    assert len(posting.description_text) > 0
    assert len(posting.description_text) < len(posting.description_html)


def test_published_on_parsed_to_utc_midnight(scraped_at: datetime) -> None:
    job_dict = _minimal_job(published_on="2026-03-15")
    posting = mapper.to_posting(job_dict, company_name="Acme", scraped_at=scraped_at)
    assert posting.posted_at == datetime(2026, 3, 15, 0, 0, 0, tzinfo=UTC)


def test_published_on_missing_becomes_none(scraped_at: datetime) -> None:
    job_dict = _minimal_job(published_on=None)
    posting = mapper.to_posting(job_dict, company_name="Acme", scraped_at=scraped_at)
    assert posting.posted_at is None


def test_location_from_locations_array(scraped_at: datetime) -> None:
    job_dict = _minimal_job(
        locations=[{"country": "France", "city": "Paris", "countryCode": "FR"}],
        telecommuting=False,
    )
    posting = mapper.to_posting(job_dict, company_name="Acme", scraped_at=scraped_at)
    assert posting.location_raw == "Paris, France"


def test_location_remote_when_telecommuting_and_no_locations(scraped_at: datetime) -> None:
    job_dict = _minimal_job(locations=[], telecommuting=True)
    posting = mapper.to_posting(job_dict, company_name="Acme", scraped_at=scraped_at)
    assert posting.location_raw == "Remote"


def test_missing_required_field_raises(scraped_at: datetime) -> None:
    job_dict = _minimal_job()
    del job_dict["shortcode"]
    with pytest.raises(KeyError):
        mapper.to_posting(job_dict, company_name="Acme", scraped_at=scraped_at)


def test_malformed_url_raises_validation_error(scraped_at: datetime) -> None:
    job_dict = _minimal_job(url="not-a-valid-url")
    with pytest.raises(ValidationError):
        mapper.to_posting(job_dict, company_name="Acme", scraped_at=scraped_at)


def _minimal_job(**overrides) -> dict:
    base = {
        "shortcode": "ABC123",
        "url": "https://apply.workable.com/j/ABC123",
        "title": "Senior Engineer",
        "description": "<p>We are hiring.</p>",
        "published_on": "2026-01-01",
        "telecommuting": False,
        "locations": [],
        "city": None,
        "country": None,
    }
    base.update(overrides)
    return base
