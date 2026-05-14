from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from jmi.api.deps import get_app_settings
from jmi.config import Settings


def verify_ingest_token(
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
    settings: Settings = Depends(get_app_settings),
) -> None:
    """FastAPI dependency that enforces the X-Ingest-Token header on a route."""
    if settings.ingest_token is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: JMI_INGEST_TOKEN not set",
        )
    if x_ingest_token != settings.ingest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing ingest token",
        )
