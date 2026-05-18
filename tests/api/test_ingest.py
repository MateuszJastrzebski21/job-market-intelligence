"""Tests for POST /api/ingest."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _posting_in(source_id: str = "jjit-1", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_id": source_id,
        "url": "https://justjoin.it/job-offer/example",
        "title": "Python Developer",
        "company_name": "Acme",
        "location_raw": "Warsaw, Hybrid",
        "salary_raw": "16000-24000 PLN",
        "raw_payload": {"foo": "bar"},
    }
    base.update(overrides)
    return base


def test_inserts_new_posting_with_null_description(
    client: TestClient, auth_headers: dict[str, str], in_memory_repo: Any
) -> None:
    body = {"source": "jjit", "postings": [_posting_in("jjit-1")]}
    response = client.post("/api/ingest", json=body, headers=auth_headers)
    assert response.status_code == 200
    out = response.json()
    assert out["accepted"] == 1
    assert out["skipped_existing"] == 0
    assert out["invalid"] == []
    assert out["accepted_indices"] == [0]

    stored = in_memory_repo.get_by_source("jjit", "jjit-1")
    assert stored is not None
    assert stored.description_html is None
    assert stored.description_text is None
    assert stored.raw_payload["foo"] == "bar"
    assert stored.raw_payload["salary_raw"] == "16000-24000 PLN"


def test_accepted_indices_excludes_skipped_existing(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """accepted_indices lists only the freshly inserted indices, not skipped ones."""
    # Pre-insert one posting
    seed_body = {"source": "jjit", "postings": [_posting_in("jjit-existing")]}
    client.post("/api/ingest", json=seed_body, headers=auth_headers)

    # Submit a batch where index 0 is the existing one and index 1 is new
    batch_body = {
        "source": "jjit",
        "postings": [_posting_in("jjit-existing"), _posting_in("jjit-fresh")],
    }
    response = client.post("/api/ingest", json=batch_body, headers=auth_headers)
    out = response.json()
    assert out["accepted"] == 1
    assert out["skipped_existing"] == 1
    assert out["accepted_indices"] == [1]  # only the fresh one


def test_skips_existing_posting(client: TestClient, auth_headers: dict[str, str]) -> None:
    body = {"source": "jjit", "postings": [_posting_in("jjit-dup")]}
    first = client.post("/api/ingest", json=body, headers=auth_headers)
    assert first.json()["accepted"] == 1
    second = client.post("/api/ingest", json=body, headers=auth_headers)
    out = second.json()
    assert out["accepted"] == 0
    assert out["skipped_existing"] == 1


def test_rejects_missing_token(client: TestClient) -> None:
    body = {"source": "jjit", "postings": [_posting_in()]}
    response = client.post("/api/ingest", json=body)
    assert response.status_code == 401


def test_rejects_wrong_token(client: TestClient) -> None:
    body = {"source": "jjit", "postings": [_posting_in()]}
    response = client.post("/api/ingest", json=body, headers={"X-Ingest-Token": "nope"})
    assert response.status_code == 401


def test_rejects_unknown_source_literal_via_pydantic(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    body = {"source": "monster_dot_com", "postings": [_posting_in()]}
    response = client.post("/api/ingest", json=body, headers=auth_headers)
    assert response.status_code == 422


def test_accepts_all_widened_sources(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Source widening verification: jjit / nofluff / linkedin all accepted."""
    for source in ("jjit", "nofluff", "linkedin"):
        body = {
            "source": source,
            "postings": [_posting_in(f"{source}-1")],
        }
        response = client.post("/api/ingest", json=body, headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] == 1


def test_batch_per_item_isolation(
    client: TestClient, auth_headers: dict[str, str], in_memory_repo: Any
) -> None:
    """Two postings: one fresh, one duplicate. Fresh one still lands."""
    first_body = {"source": "jjit", "postings": [_posting_in("a")]}
    client.post("/api/ingest", json=first_body, headers=auth_headers)

    batch_body = {
        "source": "jjit",
        "postings": [_posting_in("a"), _posting_in("b")],
    }
    response = client.post("/api/ingest", json=batch_body, headers=auth_headers)
    out = response.json()
    assert out["accepted"] == 1
    assert out["skipped_existing"] == 1
    assert in_memory_repo.get_by_source("jjit", "b") is not None
