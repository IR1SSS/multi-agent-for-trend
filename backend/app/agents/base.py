from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentContext:
    """Shared context passed between agents in a pipeline."""

    task_id: int = 0
    keyword_id: int = 0
    keyword: str = ""
    platform: str = ""
    domain_id: int = 0
    account_id: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result returned by an agent execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    skill_used: str = ""  # Track which skill strategy was used


class BaseAgent(ABC):
    """Base class for all agents in the Multi-Agent system.

    Agents are thin orchestrators that delegate to pluggable Skills
    based on the domain configuration. They look up the appropriate
    skill via the SkillRegistry and pass domain-specific config.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging and identification."""
        ...

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute the agent's logic.

        Args:
            context: Shared context from previous agents or caller.

        Returns:
            AgentResult with success status and output data.
        """
        ...

    async def _resolve_domain_config(self, context: AgentContext):
        """Resolve domain configuration for the current context.

        Returns a ResolvedDomainConfig or None if resolution fails.
        """
        if not context.domain_id:
            return None
        try:
            from app.domain_meta.config_parser import DomainConfigParser
            from app.infrastructure.database.connection import async_session_factory
            from app.infrastructure.repositories.domain_repo_impl import DomainConfigRepositoryImpl

            async with async_session_factory() as session:
                repo = DomainConfigRepositoryImpl(session)
                return await DomainConfigParser.parse(context.domain_id, repo)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[{self.name}] Failed to resolve domain config: {e}")
            return None
