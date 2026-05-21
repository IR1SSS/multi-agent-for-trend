"""Domain configuration parser.

Loads, validates, and resolves domain configurations from the database
or JSON files. Produces strongly-typed ResolvedDomainConfig objects.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.domain_meta.models import (
    DomainConfigRead,
    ResolvedDomainConfig,
    ExpanderSkillConfig,
    CleaningSkillConfig,
    InsightSkillConfig,
)

logger = logging.getLogger(__name__)


class DomainConfigParser:
    """Parses and resolves domain configurations.

    Can load from:
    1. Database (via DomainConfigRead from repository)
    2. JSON file (for seed data / CLI usage)

    After loading, the parser validates all skill sub-configs and fills
    in default values, producing a strongly-typed ResolvedDomainConfig.
    """

    @staticmethod
    async def parse(domain_id: int, repo=None) -> ResolvedDomainConfig:
        """Parse a domain configuration from the database by ID.

        Args:
            domain_id: The domain_configs.id to look up.
            repo: DomainConfigRepositoryImpl instance (must be provided for DB access).

        Returns:
            ResolvedDomainConfig with all fields validated and defaults filled.

        Raises:
            ValueError: If domain_id is not found.
        """
        if repo is None:
            raise ValueError("Repository must be provided for DB-based parsing")

        read = await repo.get_by_id(domain_id)
        if not read:
            raise ValueError(f"Domain config not found: id={domain_id}")

        return DomainConfigParser._resolve(read)

    @staticmethod
    async def parse_by_domain(domain: str, repo=None) -> ResolvedDomainConfig:
        """Parse a domain configuration by domain name.

        Args:
            domain: The domain identifier string (e.g. 'beauty').
            repo: DomainConfigRepositoryImpl instance.

        Returns:
            ResolvedDomainConfig.

        Raises:
            ValueError: If domain is not found.
        """
        if repo is None:
            raise ValueError("Repository must be provided for DB-based parsing")

        read = await repo.get_by_domain(domain)
        if not read:
            raise ValueError(f"Domain config not found: domain={domain}")

        return DomainConfigParser._resolve(read)

    @staticmethod
    def parse_from_json(json_path: str | Path) -> ResolvedDomainConfig:
        """Parse a domain configuration from a JSON file.

        Useful for seed data loading and CLI standalone mode.

        Args:
            json_path: Path to the domain configuration JSON file.

        Returns:
            ResolvedDomainConfig.

        Raises:
            FileNotFoundError: If the JSON file doesn't exist.
            ValueError: If the JSON content is invalid.
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Domain config JSON not found: {json_path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Build a DomainConfigRead-compatible dict (without id/created_at/updated_at)
        read = DomainConfigRead(
            id=0,  # Placeholder — not from DB
            domain=raw["domain"],
            display_name=raw["display_name"],
            domain_description=raw.get("domain_description", ""),
            status=raw.get("status", "active"),
            expander_skill=raw.get("expander_skill", {}),
            cleaning_skill=raw.get("cleaning_skill", {}),
            insight_skill=raw.get("insight_skill", {}),
            created_at=None,  # type: ignore
            updated_at=None,  # type: ignore
        )

        return DomainConfigParser._resolve(read)

    @staticmethod
    def _resolve(read: DomainConfigRead) -> ResolvedDomainConfig:
        """Resolve a DomainConfigRead into a fully validated ResolvedDomainConfig."""
        try:
            resolved = ResolvedDomainConfig.from_domain_config_read(read)
            logger.info(
                f"[DomainConfigParser] Resolved domain '{read.domain}' "
                f"(id={read.id}, strategy={resolved.expander_skill.strategy})"
            )
            return resolved
        except Exception as e:
            logger.error(f"[DomainConfigParser] Failed to resolve domain config: {e}")
            raise ValueError(f"Invalid domain config for '{read.domain}': {e}") from e
