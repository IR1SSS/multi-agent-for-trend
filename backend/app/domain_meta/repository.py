"""Domain configuration repository interface.

Defines the contract for domain configuration persistence.
"""
from __future__ import annotations

from typing import Optional, Protocol, Sequence

from app.domain_meta.models import DomainConfigRead


class DomainConfigRepository(Protocol):
    """Repository interface for domain configuration persistence."""

    async def get_by_id(self, domain_id: int) -> Optional[DomainConfigRead]: ...

    async def get_by_domain(self, domain: str) -> Optional[DomainConfigRead]: ...

    async def list_all(self, status: Optional[str] = None) -> Sequence[DomainConfigRead]: ...

    async def create(self, data: dict) -> DomainConfigRead: ...

    async def update(self, domain_id: int, data: dict) -> Optional[DomainConfigRead]: ...

    async def delete(self, domain_id: int) -> bool: ...
