from __future__ import annotations

from typing import Protocol, TypeVar
from uuid import UUID

T = TypeVar("T")


class AbstractRepository(Protocol[T]):
    """Minimal repository contract. Concrete repos add source-specific lookups."""

    def add(self, item: T) -> T: ...

    def get(self, id: UUID) -> T | None: ...

    def list(self, limit: int = 100, offset: int = 0) -> list[T]: ...
