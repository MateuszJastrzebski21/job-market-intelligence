"""Tests for the lazy DB engine accessor (get_engine)."""
from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine

import jmi.db.base as db_base
from jmi.db.base import get_engine


@pytest.fixture(autouse=True)
def _isolate_engine_cache() -> Iterator[None]:
    """get_engine is process-cached; clear it around each test for isolation."""
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


def _fake_settings() -> SimpleNamespace:
    return SimpleNamespace(database_url="sqlite:///:memory:")


def test_get_engine_returns_an_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_base, "get_settings", _fake_settings)
    assert isinstance(get_engine(), Engine)


def test_get_engine_is_a_cached_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_base, "get_settings", _fake_settings)
    assert get_engine() is get_engine()
