import time
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from jmi import __version__
from jmi.api.routes import details, health, ingest

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """FastAPI factory for the JMI ingest service.

    Routes are mounted under ``/api/...``. CORS is permitted only for
    ``chrome-extension://`` origins (no credentials). All requests get a
    structured log line with method, path, status, and latency.
    """
    app = FastAPI(title="JMI Ingest API", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"chrome-extension://.*",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Ingest-Token"],
        allow_credentials=False,
        max_age=3600,
    )

    @app.middleware("http")
    async def log_requests(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "api.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        return response

    app.include_router(health.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(details.router, prefix="/api")

    return app
