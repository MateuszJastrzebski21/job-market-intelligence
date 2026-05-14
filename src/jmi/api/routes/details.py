from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from jmi.api.auth import verify_ingest_token
from jmi.api.deps import get_posting_repo
from jmi.api.schemas import DetailsBatchIn, DetailsBatchOut, InvalidEntry
from jmi.storage.jobs import JobPostingRepository

router = APIRouter()
log = structlog.get_logger(__name__)


@router.post(
    "/details",
    response_model=DetailsBatchOut,
    dependencies=[Depends(verify_ingest_token)],
)
def details(
    batch: DetailsBatchIn,
    repo: JobPostingRepository = Depends(get_posting_repo),
) -> DetailsBatchOut:
    """Batch update existing postings with detail-page content.

    Looks up each detail by ``(source, source_id)``. Unknown lookups count as
    ``skipped_unknown`` (extension shouldn't POST details for postings we
    don't have, but the response stays defensive). ``raw_payload`` is merged:
    existing top-level keys preserved, ``raw_payload_patch`` from the request
    is nested under ``raw_payload['detail']``.
    """
    log.info("details.received", source=batch.source, count=len(batch.details))
    updated = 0
    skipped_unknown = 0
    invalid: list[InvalidEntry] = []

    for idx, item in enumerate(batch.details):
        try:
            existing = repo.get_by_source(batch.source, item.source_id)
            if existing is None:
                skipped_unknown += 1
                log.info(
                    "details.skip.unknown",
                    source=batch.source,
                    source_id=item.source_id,
                )
                continue

            merged_payload = {**existing.raw_payload, "detail": item.raw_payload_patch}
            repo.update_description(
                posting_id=existing.id,
                description_html=item.description_html,
                description_text=item.description_text,
                raw_payload=merged_payload,
            )
            updated += 1
        except Exception as exc:
            log.warning(
                "details.skip.error",
                source=batch.source,
                idx=idx,
                source_id=item.source_id,
                error=str(exc),
            )
            invalid.append(InvalidEntry(idx=idx, error=str(exc)))

    log.info(
        "details.done",
        source=batch.source,
        updated=updated,
        skipped_unknown=skipped_unknown,
        invalid=len(invalid),
    )
    return DetailsBatchOut(
        updated=updated,
        skipped_unknown=skipped_unknown,
        invalid=invalid,
    )
