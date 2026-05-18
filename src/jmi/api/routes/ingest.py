from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends
from pydantic import ValidationError

from jmi.api.auth import verify_ingest_token
from jmi.api.deps import get_posting_repo
from jmi.api.schemas import IngestBatchIn, IngestBatchOut, InvalidEntry
from jmi.models.job import JobPosting
from jmi.storage.jobs import JobPostingRepository

router = APIRouter()
log = structlog.get_logger(__name__)


@router.post(
    "/ingest",
    response_model=IngestBatchOut,
    dependencies=[Depends(verify_ingest_token)],
)
def ingest(
    batch: IngestBatchIn,
    repo: JobPostingRepository = Depends(get_posting_repo),
) -> IngestBatchOut:
    """Batch insert partial JobPostings (URL + listing metadata, NULL descriptions).

    Per-posting failures (Pydantic validation when constructing JobPosting, DB
    errors) are isolated to that index; the rest of the batch still applies.
    Idempotent via ``repo.get_by_source(source, source_id)`` skip-if-exists.
    """
    log.info("ingest.received", source=batch.source, count=len(batch.postings))
    accepted = 0
    skipped_existing = 0
    invalid: list[InvalidEntry] = []
    accepted_indices: list[int] = []
    now = datetime.now(tz=UTC)

    for idx, item in enumerate(batch.postings):
        try:
            if repo.get_by_source(batch.source, item.source_id) is not None:
                skipped_existing += 1
                log.debug(
                    "ingest.skip.existing",
                    source=batch.source,
                    source_id=item.source_id,
                )
                continue

            raw_payload = dict(item.raw_payload)
            if item.salary_raw is not None:
                raw_payload.setdefault("salary_raw", item.salary_raw)

            posting = JobPosting(
                source=batch.source,
                source_job_id=item.source_id,
                url=item.url,
                title=item.title,
                company_name=item.company_name,
                location_raw=item.location_raw,
                description_html=None,
                description_text=None,
                posted_at=item.posted_at,
                scraped_at=now,
                raw_payload=raw_payload,
            )
            repo.add(posting)
            accepted += 1
            accepted_indices.append(idx)
        except ValidationError as exc:
            log.warning(
                "ingest.skip.invalid",
                source=batch.source,
                idx=idx,
                source_id=item.source_id,
                errors=exc.errors(),
            )
            invalid.append(InvalidEntry(idx=idx, error=str(exc)))
        except Exception as exc:
            log.warning(
                "ingest.skip.error",
                source=batch.source,
                idx=idx,
                source_id=item.source_id,
                error=str(exc),
            )
            invalid.append(InvalidEntry(idx=idx, error=str(exc)))

    log.info(
        "ingest.done",
        source=batch.source,
        accepted=accepted,
        skipped_existing=skipped_existing,
        invalid=len(invalid),
    )
    return IngestBatchOut(
        accepted=accepted,
        skipped_existing=skipped_existing,
        invalid=invalid,
        accepted_indices=accepted_indices,
    )
