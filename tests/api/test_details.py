"""Tests for POST /api/details."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _ingest_jjit_one(
    client: TestClient, headers: dict[str, str], source_id: str = "jjit-1"
) -> None:
    body = {
        "source": "jjit",
        "postings": [
            {
                "source_id": source_id,
                "url": f"https://justjoin.it/job-offer/{source_id}",
                "title": "Python Developer",
                "company_name": "Acme",
                "location_raw": "Warsaw, Hybrid",
                "salary_raw": "16000-24000 PLN",
                "raw_payload": {"foo": "bar"},
            }
        ],
    }
    client.post("/api/ingest", json=body, headers=headers)


def test_updates_existing_posting_and_merges_raw_payload(
    client: TestClient, auth_headers: dict[str, str], in_memory_repo: Any
) -> None:
    _ingest_jjit_one(client, auth_headers, source_id="jjit-1")
    body = {
        "source": "jjit",
        "details": [
            {
                "source_id": "jjit-1",
                "description_html": "<p>Full job description</p>",
                "description_text": "Full job description",
                "raw_payload_patch": {"body_chars": 1234, "company_size": "11-50"},
            }
        ],
    }
    response = client.post("/api/details", json=body, headers=auth_headers)
    assert response.status_code == 200
    out = response.json()
    assert out["updated"] == 1
    assert out["skipped_unknown"] == 0

    stored = in_memory_repo.get_by_source("jjit", "jjit-1")
    assert stored.description_html == "<p>Full job description</p>"
    assert stored.description_text == "Full job description"
    # raw_payload merge: existing top-level keys preserved, patch nested under 'detail'
    assert stored.raw_payload["foo"] == "bar"
    assert stored.raw_payload["salary_raw"] == "16000-24000 PLN"
    assert stored.raw_payload["detail"] == {
        "body_chars": 1234,
        "company_size": "11-50",
    }


def test_skips_unknown_source_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    body = {
        "source": "jjit",
        "details": [
            {
                "source_id": "never-ingested",
                "description_html": "<p>html</p>",
                "description_text": "text",
                "raw_payload_patch": {},
            }
        ],
    }
    response = client.post("/api/details", json=body, headers=auth_headers)
    assert response.status_code == 200
    out = response.json()
    assert out["updated"] == 0
    assert out["skipped_unknown"] == 1


def test_rejects_missing_token(client: TestClient) -> None:
    body = {
        "source": "jjit",
        "details": [
            {
                "source_id": "anything",
                "description_html": "<p>html</p>",
                "description_text": "text",
                "raw_payload_patch": {},
            }
        ],
    }
    response = client.post("/api/details", json=body)
    assert response.status_code == 401
