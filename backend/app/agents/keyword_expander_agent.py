from __future__ import annotations

import logging
from typing import Optional

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.domain_meta.registry import get_registry
from app.skills.base import SkillContext

logger = logging.getLogger(__name__)

# Fallback template kept for backward compatibility when no domain config is available
KEYWORD_EXPANSION_USER_TEMPLATE = """原始关键词: {original_keyword}
主题簇: {topic_cluster}
趋势类型: {trend_type}
已有变体: {existing_variants}

请生成扩充后的搜索词，严格按以下JSON格式返回：
{{"expanded_keywords": ["搜索词1", "搜索词2", "搜索词3"]}}"""


class KeywordExpanderAgent(BaseAgent):
    """Agent responsible for expanding trend keywords into domain-specific
    search terms using pluggable ExpanderSkill.

    This agent delegates to the skill specified by the domain configuration:
    - 'hierarchical' strategy for mature industries (beauty, personal care)
    - 'tech_term' strategy for emerging industries (new energy vehicles, AI tools)

    Falls back to the 'hierarchical' skill if no domain config is available.
    """

    @property
    def name(self) -> str:
        return "KeywordExpanderAgent"

    async def execute(self, context: AgentContext) -> AgentResult:
        """Expand a keyword using the domain-configured skill strategy.

        Expects context to have:
        - keyword: The original trend keyword
        - domain_id: The domain configuration ID
        - extra['topic_cluster']: Topic cluster
        - extra['trend_type']: Trend type
        - extra['query_variants']: Pipe-separated existing variants
        """
        keyword = context.keyword
        if not keyword:
            return AgentResult(success=False, error="Missing keyword in context")

        # Resolve domain config to determine which skill to use
        domain_config = await self._resolve_domain_config(context)

        if domain_config:
            strategy = domain_config.expander_skill.strategy
            domain_name = domain_config.display_name
            negative_keywords = domain_config.expander_skill.negative_keywords
            max_depth = domain_config.expander_skill.max_depth
            levels = domain_config.expander_skill.levels
        else:
            # Fallback: use adaptive strategy with generic defaults
            strategy = "adaptive"
            domain_name = "通用"
            negative_keywords = []
            max_depth = 2
            levels = []

        # Look up the skill from the registry
        registry = get_registry()
        skill_cls = registry.get_skill("expander", strategy)

        if not skill_cls:
            logger.warning(f"[{self.name}] No skill registered for ('expander', '{strategy}'), falling back to 'adaptive'")
            skill_cls = registry.get_skill("expander", "adaptive")

        if not skill_cls:
            return AgentResult(success=False, error=f"No expander skill available for strategy: {strategy}")

        # Execute the skill
        skill = skill_cls()
        skill_context = SkillContext(
            domain_id=context.domain_id,
            keyword=keyword,
            extra={
                **context.extra,
                "domain_name": domain_name,
                "negative_keywords": negative_keywords,
                "max_depth": max_depth,
                "levels": levels,
            },
        )
        skill_config = {
            "domain_name": domain_name,
            "negative_keywords": negative_keywords,
            "max_depth": max_depth,
            "levels": levels,
        }

        try:
            skill_result = await skill.execute(skill_context, skill_config)

            if skill_result.success:
                return AgentResult(
                    success=True,
                    data=skill_result.data,
                    skill_used=f"expander:{strategy}",
                )
            else:
                # Fallback: use original keyword only
                return AgentResult(
                    success=True,
                    data={
                        "original_keyword": keyword,
                        "expanded_keywords": [],
                        "merged_keywords": [keyword],
                        "keywords_for_crawler": keyword,
                    },
                    skill_used=f"expander:{strategy} (fallback)",
                )

        except Exception as e:
            logger.error(f"[{self.name}] Skill execution failed for '{keyword}': {e}")
            return AgentResult(
                success=True,
                data={
                    "original_keyword": keyword,
                    "expanded_keywords": [],
                    "merged_keywords": [keyword],
                    "keywords_for_crawler": keyword,
                },
                skill_used=f"expander:{strategy} (error fallback)",
            )
