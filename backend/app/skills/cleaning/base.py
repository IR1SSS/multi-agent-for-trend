"""Base cleaning skill — abstract interface for data cleaning strategies.

All cleaning skills must:
1. Accept raw data items + domain config
2. Generate dynamic prompts based on required_entities
3. Return cleaned results with entity extraction
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.skills.base import BaseSkill, SkillContext, SkillResult


class BaseCleaningSkill(BaseSkill):
    """Abstract base class for data cleaning skills."""

    @property
    def skill_type(self) -> str:
        return "cleaning"

    @abstractmethod
    async def clean_item(
        self,
        item: dict[str, Any],
        domain_name: str,
        required_entities: list[str],
        noise_filters: list[str],
        domain_description: str = "",
    ) -> dict[str, Any] | None:
        """Clean a single raw data item.

        Args:
            item: Raw data dict with title, desc, etc.
            domain_name: Domain display name for prompt context.
            required_entities: Entity types to extract.
            noise_filters: Noise detection rules.
            domain_description: Domain description for adaptive skill inference.

        Returns:
            Cleaned result dict, or None if the item is noise.
        """
        ...

    @abstractmethod
    async def generate_prompt(
        self,
        domain_name: str,
        required_entities: list[str],
        noise_filters: list[str],
        title: str,
        desc: str,
        domain_description: str = "",
    ) -> str:
        """Generate a domain-aware cleaning prompt.

        Args:
            domain_name: The domain's display name.
            required_entities: Entity types to extract.
            noise_filters: Noise detection rules.
            title: Content title.
            desc: Content description.
            domain_description: Domain description for adaptive skill inference.

        Returns:
            The formatted prompt string.
        """
        ...

    async def execute(self, context: SkillContext, config: dict) -> SkillResult:
        """Default execute: clean raw items from context.extra['raw_items']."""
        raw_items = context.extra.get("raw_items", [])
        domain_name = config.get("domain_name", "")
        required_entities = config.get("required_entities", [])
        noise_filters = config.get("noise_filters", [])
        domain_description = config.get("domain_description", "")

        if not raw_items:
            return SkillResult(success=True, data={"cleaned_count": 0, "cleaned_items": []})

        cleaned_items = []
        for item in raw_items:
            result = await self.clean_item(item, domain_name, required_entities, noise_filters, domain_description=domain_description)
            if result is not None:
                cleaned_items.append(result)

        return SkillResult(
            success=True,
            data={
                "cleaned_count": len(cleaned_items),
                "cleaned_items": cleaned_items,
            },
        )
