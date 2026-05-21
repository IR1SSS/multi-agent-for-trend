"""Domain configuration API endpoints.

CRUD operations for domain configurations, including
domain activation, skill configuration management,
keyword generation, and CSV import.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain_meta.models import DomainConfigCreate, DomainConfigUpdate, DomainConfigRead
from app.domain_meta.keyword_generator import KeywordGenerator
from app.infrastructure.database.connection import get_session
from app.infrastructure.repositories.domain_repo_impl import DomainConfigRepositoryImpl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["domains"])


def _get_repo(session: AsyncSession = Depends(get_session)) -> DomainConfigRepositoryImpl:
    return DomainConfigRepositoryImpl(session)


@router.get("", response_model=list[DomainConfigRead])
async def list_domains(
    status: Optional[str] = Query(default=None, pattern=r"^(active|archived)$"),
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
):
    """List all domain configurations, optionally filtered by status."""
    domains = await repo.list_all(status=status)
    return list(domains)


@router.post("", response_model=DomainConfigRead, status_code=201)
async def create_domain(
    body: DomainConfigCreate,
    auto_generate_keywords: bool = Query(default=True, description="Auto-generate seed keywords after domain creation"),
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
    session: AsyncSession = Depends(get_session),
):
    """Create a new domain configuration.

    When auto_generate_keywords=True (default), seed keywords are
    automatically generated via LLM after domain creation.
    """
    # Check if domain already exists
    existing = await repo.get_by_domain(body.domain)
    if existing:
        raise HTTPException(status_code=409, detail=f"Domain '{body.domain}' already exists")

    data = body.model_dump()
    # Propagate domain_description into skill configs for adaptive strategy
    desc = body.domain_description or ""
    if body.expander_skill.strategy == "adaptive" and not body.expander_skill.domain_description:
        data["expander_skill"]["domain_description"] = desc
    if body.cleaning_skill.strategy == "adaptive" and not body.cleaning_skill.domain_description:
        data["cleaning_skill"]["domain_description"] = desc

    # Serialize nested Pydantic models to dicts for JSON columns
    data["expander_skill"] = body.expander_skill.model_dump()
    data["cleaning_skill"] = body.cleaning_skill.model_dump()
    data["insight_skill"] = body.insight_skill.model_dump()

    # Re-apply domain_description propagation after model_dump
    if body.expander_skill.strategy == "adaptive" and not body.expander_skill.domain_description:
        data["expander_skill"]["domain_description"] = desc
    if body.cleaning_skill.strategy == "adaptive" and not body.cleaning_skill.domain_description:
        data["cleaning_skill"]["domain_description"] = desc

    created = await repo.create(data)

    # Auto-generate seed keywords if requested
    if auto_generate_keywords and desc:
        try:
            generator = KeywordGenerator()
            await generator.generate(
                session=session,
                domain_id=created.id,
                domain_name=body.display_name,
                domain_description=desc,
            )
            logger.info(f"[Domains] Auto-generated keywords for domain '{body.domain}'")
        except Exception as e:
            logger.warning(f"[Domains] Failed to auto-generate keywords: {e}")

    return created


@router.get("/active")
async def get_active_domain():
    """Get the currently active domain ID."""
    try:
        import redis
        from app.config.settings import settings

        r = redis.from_url(settings.REDIS_URL)
        domain_id = r.get("active_domain_id")
        if domain_id:
            return {"active_domain_id": int(domain_id)}
        return {"active_domain_id": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active domain: {e}")


@router.get("/{domain_id}", response_model=DomainConfigRead)
async def get_domain(
    domain_id: int,
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
):
    """Get a domain configuration by ID."""
    domain = await repo.get_by_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain not found: id={domain_id}")
    return domain


@router.put("/{domain_id}", response_model=DomainConfigRead)
async def update_domain(
    domain_id: int,
    body: DomainConfigUpdate,
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
):
    """Update a domain configuration."""
    # Build update data, only including non-None fields
    update_data = {}
    if body.display_name is not None:
        update_data["display_name"] = body.display_name
    if body.domain_description is not None:
        update_data["domain_description"] = body.domain_description
    if body.status is not None:
        update_data["status"] = body.status
    if body.expander_skill is not None:
        update_data["expander_skill"] = body.expander_skill.model_dump()
    if body.cleaning_skill is not None:
        update_data["cleaning_skill"] = body.cleaning_skill.model_dump()
    if body.insight_skill is not None:
        update_data["insight_skill"] = body.insight_skill.model_dump()

    result = await repo.update(domain_id, update_data)
    if not result:
        raise HTTPException(status_code=404, detail=f"Domain not found: id={domain_id}")
    return result


@router.delete("/{domain_id}")
async def archive_domain(
    domain_id: int,
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
):
    """Archive (soft-delete) a domain configuration."""
    success = await repo.delete(domain_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Domain not found: id={domain_id}")
    return {"success": True, "message": f"Domain {domain_id} archived"}


@router.post("/{domain_id}/activate")
async def activate_domain(domain_id: int):
    """Set a domain as the currently active domain.

    This stores the active domain ID in Redis for quick lookup
    by all agents and tasks.
    """
    try:
        import redis
        from app.config.settings import settings

        r = redis.from_url(settings.REDIS_URL)
        r.set("active_domain_id", str(domain_id))
        return {"success": True, "active_domain_id": domain_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate domain: {e}")


@router.post("/{domain_id}/generate-keywords")
async def generate_keywords(
    domain_id: int,
    num_keywords: int = Query(default=15, ge=5, le=50, description="Number of keywords to generate"),
    session: AsyncSession = Depends(get_session),
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
):
    """Manually trigger LLM-based keyword generation for a domain."""
    domain = await repo.get_by_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain not found: id={domain_id}")

    generator = KeywordGenerator()
    keywords = await generator.generate(
        session=session,
        domain_id=domain_id,
        domain_name=domain.display_name,
        domain_description=domain.domain_description or "",
        num_keywords=num_keywords,
    )
    return {"success": True, "domain_id": domain_id, "keywords_generated": len(keywords), "keywords": keywords}


@router.post("/{domain_id}/import-keywords")
async def import_keywords(
    domain_id: int,
    file: UploadFile = File(..., description="CSV file with keyword columns"),
    session: AsyncSession = Depends(get_session),
    repo: DomainConfigRepositoryImpl = Depends(_get_repo),
):
    """Import keywords from a CSV file for a domain."""
    domain = await repo.get_by_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain not found: id={domain_id}")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="CSV file must be UTF-8 or GBK encoded")

    generator = KeywordGenerator()
    keywords = await generator.import_csv(
        session=session,
        domain_id=domain_id,
        csv_content=csv_text,
    )
    return {"success": True, "domain_id": domain_id, "keywords_imported": len(keywords), "keywords": keywords}


@router.get("/{domain_id}/keywords")
async def list_keywords(
    domain_id: int,
    active_only: bool = Query(default=True, description="Only return active keywords"),
    session: AsyncSession = Depends(get_session),
):
    """List keywords for a domain."""
    generator = KeywordGenerator()
    keywords = await generator.list_keywords(
        session=session,
        domain_id=domain_id,
        active_only=active_only,
    )
    return {"domain_id": domain_id, "keywords": keywords, "total": len(keywords)}
