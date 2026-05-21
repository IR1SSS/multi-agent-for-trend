"""Skill base classes and shared types.

Defines the fundamental abstractions for the pluggable skill architecture:
- BaseSkill: Abstract base class for all skills
- SkillContext: Input context passed to skills
- SkillResult: Output returned by skills
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillContext:
    """Input context passed to a skill's execute method.

    Carries the domain configuration and task-specific data.
    """

    domain_id: int = 0
    keyword: str = ""
    platform: str = ""
    task_id: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result returned by a skill execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base class for all skills in the pluggable architecture.

    Each skill implementation must:
    1. Set the `skill_type` property (e.g. 'expander', 'crawler')
    2. Set the `strategy_name` property (e.g. 'hierarchical', 'tech_term')
    3. Implement the `execute` method
    """

    @property
    @abstractmethod
    def skill_type(self) -> str:
        """Skill category identifier (e.g. 'expander', 'crawler', 'cleaning', 'insight')."""
        ...

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Strategy name within the skill type (e.g. 'hierarchical', 'tech_term')."""
        ...

    @abstractmethod
    async def execute(self, context: SkillContext, config: dict) -> SkillResult:
        """Execute the skill's logic.

        Args:
            context: Input context with domain_id, keyword, platform, etc.
            config: The skill-specific configuration from domain_config (e.g. expander_skill dict).

        Returns:
            SkillResult with success status and output data.
        """
        ...
