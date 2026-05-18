"""Tests for Settings validation and the get_settings cache."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jmi.config import Settings, get_settings


def test_empty_database_url_is_rejected() -> None:
    """An empty DATABASE_URL must fail loudly — no default credential fallback."""
    with pytest.raises(ValidationError):
        Settings(database_url="")


def test_valid_database_url_is_accepted() -> None:
    settings = Settings(database_url="postgresql+psycopg://u:p@localhost:5432/db")
    assert settings.database_url == "postgresql+psycopg://u:p@localhost:5432/db"


def test_get_settings_is_cached() -> None:
    """get_settings() returns the same Settings instance on repeated calls."""
    get_settings.cache_clear()
    try:
        first = get_settings()
        second = get_settings()
        assert first is second
    finally:
        get_settings.cache_clear()
