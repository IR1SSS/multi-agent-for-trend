"""Skill registry — dynamic lookup of skill implementations by type and strategy.

The registry maps (skill_type, strategy_name) → skill class.
Skills register themselves at import time via the @register_skill decorator
or explicitly via SkillRegistry.register().

Agents look up skills via SkillRegistry.get_skill() at runtime,
driven by the domain configuration's strategy field.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class _SkillRegistry:
    """Singleton registry for skill implementations.

    Maps (skill_type, strategy_name) → skill class.
    Thread-safe for read operations after initialization.
    """

    def __init__(self) -> None:
        self._registry: dict[tuple[str, str], type[BaseSkill]] = {}

    def register(self, skill_type: str, strategy_name: str, skill_cls: type[BaseSkill]) -> None:
        """Register a skill implementation.

        Args:
            skill_type: The skill category (e.g. 'expander', 'crawler', 'cleaning', 'insight').
            strategy_name: The strategy identifier (e.g. 'hierarchical', 'tech_term').
            skill_cls: The skill class to register.
        """
        key = (skill_type, strategy_name)
        if key in self._registry:
            logger.warning(
                f"[SkillRegistry] Overwriting existing skill: "
                f"({skill_type}, {strategy_name}) {self._registry[key].__name__} → {skill_cls.__name__}"
            )
        self._registry[key] = skill_cls
        logger.debug(f"[SkillRegistry] Registered skill: ({skill_type}, {strategy_name}) → {skill_cls.__name__}")

    def get_skill(self, skill_type: str, strategy_name: str) -> Optional[type[BaseSkill]]:
        """Look up a skill class by type and strategy.

        Args:
            skill_type: The skill category.
            strategy_name: The strategy identifier.

        Returns:
            The skill class, or None if not found.
        """
        key = (skill_type, strategy_name)
        skill_cls = self._registry.get(key)
        if not skill_cls:
            logger.warning(f"[SkillRegistry] No skill registered for ({skill_type}, {strategy_name})")
        return skill_cls

    def list_skills(self) -> dict[tuple[str, str], str]:
        """List all registered skills as {(type, strategy): class_name}."""
        return {k: cls.__name__ for k, cls in self._registry.items()}

    def is_registered(self, skill_type: str, strategy_name: str) -> bool:
        """Check if a skill is registered."""
        return (skill_type, strategy_name) in self._registry


# Module-level singleton
_skill_registry = _SkillRegistry()


def get_registry() -> _SkillRegistry:
    """Get the global skill registry singleton."""
    return _skill_registry


def register_skill(skill_type: str, strategy_name: str):
    """Decorator to register a skill class in the global registry.

    Usage:
        @register_skill("expander", "hierarchical")
        class HierarchicalExpanderSkill(BaseExpanderSkill):
            ...
    """
    def decorator(cls: type[BaseSkill]) -> type[BaseSkill]:
        _skill_registry.register(skill_type, strategy_name, cls)
        return cls
    return decorator
