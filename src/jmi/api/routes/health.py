from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from jmi import __version__
from jmi.api.deps import health_db_check
from jmi.api.schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(
    response: Response, db_ok: bool = Depends(health_db_check)
) -> HealthOut:
    """Liveness + DB-reachability probe used by the extension popup.

    Returns 503 when the DB is unreachable so monitoring/ops can alert; the
    response body still carries the structured `db_ok` signal the popup reads.
    """
    if not db_ok:
        response.status_code = 503
    return HealthOut(status="ok", db_ok=db_ok, version=__version__)
