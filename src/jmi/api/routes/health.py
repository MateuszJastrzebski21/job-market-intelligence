from __future__ import annotations

from fastapi import APIRouter, Depends

from jmi import __version__
from jmi.api.deps import health_db_check
from jmi.api.schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(db_ok: bool = Depends(health_db_check)) -> HealthOut:
    """Liveness + DB-reachability probe used by the extension popup."""
    return HealthOut(status="ok", db_ok=db_ok, version=__version__)
