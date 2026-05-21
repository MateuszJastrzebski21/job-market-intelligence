"""Tests for ``CompanyResearchCacheRepository`` (PR-3.4a)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from jmi.storage.company_research_cache import (
    CACHE_TTL_DAYS,
    CompanyResearchCacheRepository,
    CompanyResearchCacheRow,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _row(
    key: str,
    *,
    company_name: str = "Acme",
    company_domain: str | None = "acme.com",
    research_json: dict[str, object] | None = None,
    fetched_at: datetime | None = None,
) -> CompanyResearchCacheRow:
    return CompanyResearchCacheRow(
        key=key,
        company_name=company_name,
        company_domain=company_domain,
        research_json=research_json or {"confidence": "high", "summary": "ok"},
        fetched_at=fetched_at or _now(),
    )


def test_make_key_normalises_case_and_whitespace() -> None:
    k1 = CompanyResearchCacheRepository.make_key("Acme Corp", "Acme.com")
    k2 = CompanyResearchCacheRepository.make_key(" acme corp ", "acme.COM ")
    assert k1 == k2
    assert len(k1) == 64  # SHA256 hex


def test_make_key_treats_none_domain_as_empty_string() -> None:
    k_none = CompanyResearchCacheRepository.make_key("Acme", None)
    k_empty = CompanyResearchCacheRepository.make_key("Acme", "")
    assert k_none == k_empty


def test_make_key_differs_by_company() -> None:
    k1 = CompanyResearchCacheRepository.make_key("Acme", "co.com")
    k2 = CompanyResearchCacheRepository.make_key("Beta", "co.com")
    assert k1 != k2


def test_put_and_get_round_trip(db_session: Session) -> None:
    repo = CompanyResearchCacheRepository(db_session)
    key = repo.make_key("Acme", "acme.com")
    repo.put(_row(key, research_json={"confidence": "high", "x": 1}))
    fetched = repo.get(key)
    assert fetched is not None
    assert fetched.research_json == {"confidence": "high", "x": 1}
    assert fetched.company_name == "Acme"


def test_get_missing_key_returns_none(db_session: Session) -> None:
    repo = CompanyResearchCacheRepository(db_session)
    assert repo.get("a" * 64) is None


def test_get_expired_returns_none(db_session: Session) -> None:
    repo = CompanyResearchCacheRepository(db_session)
    key = repo.make_key("Old", None)
    repo.put(_row(key, fetched_at=_now() - timedelta(days=10)))

    assert repo.get(key, ttl_days=CACHE_TTL_DAYS) is None
    # explicit higher TTL still returns it
    assert repo.get(key, ttl_days=30) is not None


def test_put_upserts_existing_key(db_session: Session) -> None:
    repo = CompanyResearchCacheRepository(db_session)
    key = repo.make_key("Co", "co.com")
    repo.put(_row(key, research_json={"v": 1}))
    repo.put(_row(key, research_json={"v": 2}, company_name="Co Inc"))

    fetched = repo.get(key)
    assert fetched is not None
    assert fetched.research_json == {"v": 2}
    assert fetched.company_name == "Co Inc"


def test_purge_expired_removes_old_rows(db_session: Session) -> None:
    repo = CompanyResearchCacheRepository(db_session)
    repo.put(_row("a" * 64, fetched_at=_now() - timedelta(days=10)))
    repo.put(_row("b" * 64, fetched_at=_now() - timedelta(days=3)))
    repo.put(_row("c" * 64, fetched_at=_now() - timedelta(days=14)))

    removed = repo.purge_expired(ttl_days=CACHE_TTL_DAYS)
    assert removed == 2
    # The 3-day-old row survives at the default TTL.
    assert repo.get("b" * 64) is not None
    assert repo.get("a" * 64, ttl_days=999) is None
    assert repo.get("c" * 64, ttl_days=999) is None
