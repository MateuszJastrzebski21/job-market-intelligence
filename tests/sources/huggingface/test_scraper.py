from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from jmi.models.job import JobPosting
from jmi.sources.huggingface import HuggingFaceScraper
from jmi.sources.huggingface.client import WorkableClient

FIXTURE = Path(__file__).parent / "fixtures" / "workable_response.json"


class _FakeClient:
    """Stand-in for WorkableClient that returns a canned response."""

    def __init__(self, response: dict) -> None:
        self._response = response
        self.calls: list[str] = []

    def fetch_account(self, subdomain: str) -> dict:
        self.calls.append(subdomain)
        return self._response

    def close(self) -> None:  # match protocol
        pass


class _InMemoryRepo:
    """Minimal in-memory stand-in for JobPostingRepository."""

    def __init__(self, existing_shortcodes: set[str] | None = None) -> None:
        self._existing = existing_shortcodes or set()
        self.added: list[JobPosting] = []

    def get_by_source(self, source: str, source_job_id: str) -> JobPosting | None:
        if source_job_id in self._existing:
            return _stub_posting(source_job_id)
        return None

    def add(self, posting: JobPosting) -> JobPosting:
        self.added.append(posting)
        return posting


@pytest.fixture
def workable_response() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_inserts_all_new_jobs(workable_response: dict) -> None:
    client = _FakeClient(workable_response)
    repo = _InMemoryRepo()
    scraper = HuggingFaceScraper(client=client)  # type: ignore[arg-type]

    stats = scraper.run(repo)  # type: ignore[arg-type]

    expected = len(workable_response["jobs"])
    assert stats.inserted == expected
    assert stats.skipped == 0
    assert stats.invalid == 0
    assert len(repo.added) == expected
    assert client.calls == ["huggingface"]


def test_skips_existing_postings(workable_response: dict) -> None:
    jobs = workable_response["jobs"]
    existing = {jobs[0]["shortcode"], jobs[1]["shortcode"]}
    client = _FakeClient(workable_response)
    repo = _InMemoryRepo(existing_shortcodes=existing)
    scraper = HuggingFaceScraper(client=client)  # type: ignore[arg-type]

    stats = scraper.run(repo)  # type: ignore[arg-type]

    assert stats.skipped == 2
    assert stats.inserted == len(jobs) - 2


def test_company_name_comes_from_class_attribute(workable_response: dict) -> None:
    client = _FakeClient(workable_response)
    repo = _InMemoryRepo()
    scraper = HuggingFaceScraper(client=client)  # type: ignore[arg-type]

    scraper.run(repo)  # type: ignore[arg-type]

    for posting in repo.added:
        assert posting.company_name == HuggingFaceScraper.SOURCE_COMPANY
        assert HuggingFaceScraper.SOURCE_COMPANY == "Hugging Face"


def test_malformed_single_job_is_skipped_not_fatal(workable_response: dict) -> None:
    broken = {**workable_response, "jobs": [*workable_response["jobs"]]}
    broken["jobs"][0] = {**broken["jobs"][0], "url": "not-a-url"}
    client = _FakeClient(broken)
    repo = _InMemoryRepo()
    scraper = HuggingFaceScraper(client=client)  # type: ignore[arg-type]

    stats = scraper.run(repo)  # type: ignore[arg-type]

    assert stats.invalid == 1
    assert stats.inserted == len(broken["jobs"]) - 1


def test_respects_limit_argument(workable_response: dict) -> None:
    client = _FakeClient(workable_response)
    repo = _InMemoryRepo()
    scraper = HuggingFaceScraper(client=client)  # type: ignore[arg-type]

    stats = scraper.run(repo, limit=2)  # type: ignore[arg-type]

    assert stats.inserted == 2


def test_client_constructor_default_builds_real_client() -> None:
    scraper = HuggingFaceScraper()
    assert isinstance(scraper._client, WorkableClient)
    scraper._client.close()


def _stub_posting(shortcode: str) -> JobPosting:
    from datetime import UTC, datetime

    return JobPosting(
        source="huggingface",
        source_job_id=shortcode,
        url="https://apply.workable.com/j/STUB",
        title="stub",
        company_name="Hugging Face",
        description_html="<p>x</p>",
        description_text="x",
        scraped_at=datetime.now(tz=UTC),
    )


def _unused_uuid() -> UUID:
    return uuid4()
