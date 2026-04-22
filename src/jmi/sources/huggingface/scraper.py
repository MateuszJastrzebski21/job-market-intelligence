from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from pydantic import ValidationError

from jmi.sources.huggingface import mapper
from jmi.sources.huggingface.client import WorkableClient
from jmi.storage.jobs import JobPostingRepository

log = structlog.get_logger(__name__)

# Log a warning once the widget endpoint returns this many jobs — a signal
# that we may be approaching Workable's undisclosed response cap and should
# investigate pagination before data silently drops.
LARGE_RESPONSE_WARNING_THRESHOLD = 50


@dataclass
class ScrapeStats:
    inserted: int = 0
    skipped: int = 0
    invalid: int = 0


class HuggingFaceScraper:
    """Scraper for Hugging Face careers via Workable's public widget API.

    Single-company source: every posting here is by Hugging Face itself, so
    `SOURCE_COMPANY` lives on the class (not the mapper) — same pattern will
    apply to any future single-company scraper (Anthropic, Cohere, ...).
    """

    SOURCE = "huggingface"
    SOURCE_COMPANY = "Hugging Face"
    WORKABLE_SUBDOMAIN = "huggingface"

    def __init__(self, client: WorkableClient | None = None) -> None:
        self._client = client or WorkableClient()
        self._owns_client = client is None

    def run(
        self,
        repo: JobPostingRepository,
        *,
        limit: int | None = None,
    ) -> ScrapeStats:
        stats = ScrapeStats()
        try:
            response = self._client.fetch_account(self.WORKABLE_SUBDOMAIN)
        finally:
            if self._owns_client:
                self._client.close()

        jobs = response.get("jobs") or []
        total = len(jobs)
        log.info("scrape.fetched", source=self.SOURCE, total=total)

        if total >= LARGE_RESPONSE_WARNING_THRESHOLD:
            log.warning(
                "scrape.large_response",
                source=self.SOURCE,
                total=total,
                threshold=LARGE_RESPONSE_WARNING_THRESHOLD,
                note="Workable widget endpoint has no pagination; investigate cap.",
            )

        scraped_at = datetime.now(tz=UTC)
        for job_dict in jobs[:limit] if limit else jobs:
            shortcode = job_dict.get("shortcode", "<missing>")
            existing = repo.get_by_source(self.SOURCE, shortcode)
            if existing is not None:
                stats.skipped += 1
                continue

            try:
                posting = mapper.to_posting(
                    job_dict,
                    company_name=self.SOURCE_COMPANY,
                    scraped_at=scraped_at,
                )
            except ValidationError as exc:
                log.warning(
                    "scrape.skip.invalid",
                    source=self.SOURCE,
                    shortcode=shortcode,
                    errors=exc.errors(),
                )
                stats.invalid += 1
                continue

            repo.add(posting)
            stats.inserted += 1

        log.info(
            "scrape.done",
            source=self.SOURCE,
            inserted=stats.inserted,
            skipped=stats.skipped,
            invalid=stats.invalid,
        )
        return stats
