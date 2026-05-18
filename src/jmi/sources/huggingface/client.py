from typing import Any

import httpx
import structlog
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger(__name__)

WIDGET_BASE = "https://apply.workable.com/api/v1/widget/accounts"
DEFAULT_TIMEOUT = 15.0


class WorkableError(Exception):
    """Raised when the Workable widget endpoint fails non-retriably
    (4xx other than 429, unparseable response, etc.)."""


class _RetriableHTTPError(Exception):
    """Internal sentinel to signal tenacity a retry is wanted."""


class WorkableClient:
    """Thin wrapper around Workable's public widget endpoint.

    Sync-only (matches our "sync first" stack decision). Retries 429/5xx/transport
    errors with exponential backoff; fails fast on other 4xx.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_attempts: int = 5,
    ) -> None:
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def __enter__(self) -> "WorkableClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_account(self, subdomain: str) -> dict[str, Any]:
        """GET /api/v1/widget/accounts/{subdomain}?details=true → parsed JSON."""
        url = f"{WIDGET_BASE}/{subdomain}"
        params = {"details": "true"}

        try:
            for attempt in Retrying(
                reraise=True,
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                retry=retry_if_exception_type(
                    (_RetriableHTTPError, httpx.TransportError, httpx.TimeoutException)
                ),
            ):
                with attempt:
                    response = self._client.get(url, params=params)
                    self._raise_if_bad(response)
        except RetryError as exc:
            raise WorkableError(f"Exhausted retries for {url}") from exc

        try:
            data: dict[str, Any] = response.json()
            return data
        except ValueError as exc:
            body_preview = response.text[:500]
            log.error(
                "workable.response.not_json",
                url=url,
                status=response.status_code,
                body_preview=body_preview,
            )
            raise WorkableError(f"Non-JSON response from {url}") from exc

    def _raise_if_bad(self, response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return

        if status == 429 or 500 <= status < 600:
            retry_after = response.headers.get("Retry-After")
            log.warning(
                "workable.retry",
                status=status,
                url=str(response.request.url),
                retry_after=retry_after,
            )
            raise _RetriableHTTPError(f"HTTP {status}")

        # 4xx (401/403/404/etc.) — fail fast
        log.error(
            "workable.fatal",
            status=status,
            url=str(response.request.url),
            body_preview=response.text[:500],
        )
        raise WorkableError(f"HTTP {status} from {response.request.url}")
