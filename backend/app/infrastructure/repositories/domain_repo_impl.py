"""Domain configuration repository implementation.

SQLAlchemy-backed implementation of the DomainConfigRepository interface.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain_meta.models import DomainConfigRead
from app.infrastructure.database.models import DomainConfig as DomainConfigORM

logger = logging.getLogger(__name__)


class DomainConfigRepositoryImpl:
    """SQLAlchemy implementation of DomainConfigRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, domain_id: int) -> Optional[DomainConfigRead]:
        row = await self._session.get(DomainConfigORM, domain_id)
        if not row:
            return None
        return self._to_read(row)

    async def get_by_domain(self, domain: str) -> Optional[DomainConfigRead]:
        stmt = select(DomainConfigORM).where(DomainConfigORM.domain == domain)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return self._to_read(row)

    async def list_all(self, status: Optional[str] = None) -> Sequence[DomainConfigRead]:
        stmt = select(DomainConfigORM).order_by(DomainConfigORM.id)
        if status:
            stmt = stmt.where(DomainConfigORM.status == status)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_read(row) for row in rows]

    async def create(self, data: dict) -> DomainConfigRead:
        row = DomainConfigORM(**data)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        logger.info(f"[DomainConfigRepo] Created domain: {row.domain} (id={row.id})")
        return self._to_read(row)

    async def update(self, domain_id: int, data: dict) -> Optional[DomainConfigRead]:
        row = await self._session.get(DomainConfigORM, domain_id)
        if not row:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(row, key, value)
        row.updated_at = datetime.now()
        await self._session.flush()
        await self._session.refresh(row)
        logger.info(f"[DomainConfigRepo] Updated domain id={domain_id}")
        return self._to_read(row)

    async def delete(self, domain_id: int) -> bool:
        row = await self._session.get(DomainConfigORM, domain_id)
        if not row:
            return False
        # Soft delete: archive instead of hard delete
        row.status = "archived"
        row.updated_at = datetime.now()
        await self._session.flush()
        logger.info(f"[DomainConfigRepo] Archived domain id={domain_id}")
        return True

    @staticmethod
    def _to_read(row: DomainConfigORM) -> DomainConfigRead:
        return DomainConfigRead(
            id=row.id,
            domain=row.domain,
            display_name=row.display_name,
            domain_description=row.domain_description or "",
            status=row.status,
            expander_skill=row.expander_skill or {},
            cleaning_skill=row.cleaning_skill or {},
            insight_skill=row.insight_skill or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
