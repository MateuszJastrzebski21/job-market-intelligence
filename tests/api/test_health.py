"""Tests for GET /api/health."""

from __future__ import annotations

from fastapi.testclient import TestClient

from jmi.api.deps import health_db_check


def test_health_returns_ok_when_db_reachable(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db_ok"] is True
    assert isinstance(body["version"], str) and body["version"]


def test_health_requires_no_token(client: TestClient) -> None:
    """The extension popup polls this endpoint on open; no auth required."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_db_ok_false_when_check_fails(client: TestClient) -> None:
    """A failed DB probe returns 503 (so monitoring can alert) but still carries
    the structured db_ok=False signal the extension popup reads."""
    client.app.dependency_overrides[health_db_check] = lambda: False
    response = client.get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "ok"
    assert body["db_ok"] is False
