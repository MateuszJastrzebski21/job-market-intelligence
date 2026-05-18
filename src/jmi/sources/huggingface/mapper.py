from datetime import UTC, date, datetime
from typing import Any

from bs4 import BeautifulSoup

from jmi.models.job import JobPosting


def to_posting(
    job_dict: dict[str, Any],
    *,
    company_name: str,
    scraped_at: datetime,
) -> JobPosting:
    """Map a Workable widget job dict to a JobPosting.

    Pure function. Raises pydantic.ValidationError on malformed input; the
    scraper catches and logs per-job failures so one broken entry doesn't
    kill the whole run.
    """
    description_html = job_dict.get("description") or ""
    description_text = _html_to_text(description_html)

    return JobPosting(
        source="huggingface",
        source_job_id=job_dict["shortcode"],
        url=job_dict["url"],
        title=job_dict["title"],
        company_name=company_name,
        location_raw=_format_location(job_dict),
        description_html=description_html,
        description_text=description_text,
        posted_at=_parse_published_on(job_dict.get("published_on")),
        scraped_at=scraped_at,
        raw_payload=job_dict,
    )


def _format_location(job_dict: dict[str, Any]) -> str | None:
    locations = job_dict.get("locations") or []
    if locations:
        first = locations[0]
        city = first.get("city") or job_dict.get("city")
        country = first.get("country") or job_dict.get("country")
        parts = [p for p in (city, country) if p]
        if parts:
            return ", ".join(parts)

    if job_dict.get("telecommuting"):
        return "Remote"

    return None


def _parse_published_on(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return datetime.combine(parsed, datetime.min.time(), tzinfo=UTC)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
