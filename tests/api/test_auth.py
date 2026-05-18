"""Tests for the X-Ingest-Token auth dependency (verify_ingest_token).

Exercises the timing-safe `hmac.compare_digest` comparison via the protected
`/api/ingest` route, plus the fail-closed behaviour when the server has no
token configured.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jmi.api.app import create_app
from jmi.api.deps import get_app_settings, get_posting_repo, health_db_check
from jmi.config import Settings


def _ingest_body() -> dict[str, Any]:
    return {
        "source": "jjit",
        "postings": [
            {
                "source_id": "auth-1",
                "url": "https://justjoin.it/job-offer/example",
                "title": "Python Developer",
                "company_name": "Acme",
            }
        ],
    }


def test_correct_token_authorizes(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/api/ingest", json=_ingest_body(), headers=auth_headers)
    assert response.status_code == 200


def test_wrong_token_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/ingest",
        json=_ingest_body(),
        headers={"X-Ingest-Token": "wrong-token"},
    )
    assert response.status_code == 401


def test_missing_token_rejected(client: TestClient) -> None:
    response = client.post("/api/ingest", json=_ingest_body())
    assert response.status_code == 401


@pytest.fixture
def client_without_configured_token(in_memory_repo: Any) -> Iterator[TestClient]:
    """Client whose server settings have no ingest_token — a misconfiguration."""
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        ingest_token=None,
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
    )
    app.dependency_overrides[get_posting_repo] = lambda: in_memory_repo
    app.dependency_overrides[health_db_check] = lambda: True
    with TestClient(app) as test_client:
        yield test_client


def test_unset_server_token_is_500(
    client_without_configured_token: TestClient,
) -> None:
    """A server with no ingest_token configured fails closed with 500."""
    response = client_without_configured_token.post(
        "/api/ingest",
        json=_ingest_body(),
        headers={"X-Ingest-Token": "anything"},
    )
    assert response.status_code == 500
