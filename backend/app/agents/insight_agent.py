from __future__ import annotations

import logging
from typing import Optional

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.domain_meta.registry import get_registry
from app.infrastructure.database.connection import async_session_factory
from app.infrastructure.repositories.trend_repo_impl import TrendRepositoryImpl
from app.skills.base import SkillContext

logger = logging.getLogger(__name__)


class InsightAgent(BaseAgent):
    """Agent responsible for trend analysis and insight generation.

    Delegates to the domain-configured InsightSkill (e.g. 'statistics'
    or 'report_generator') for statistical analysis and report generation.
    """

    @property
    def name(self) -> str:
        return "InsightAgent"

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate trend insights from cleaned data.

        Expects context to have:
        - keyword: The keyword to analyze
        - platform: Optional platform filter
        - domain_id: The domain configuration ID
        """
        keyword = context.keyword

        if not keyword:
            return AgentResult(success=False, error="Missing keyword in context")

        try:
            async with async_session_factory() as session:
                repo = TrendRepositoryImpl(session)

                platform = context.platform or None
                items = await repo.query(keyword=keyword, platform=platform, limit=100)
                total_count = await repo.count_by_keyword(keyword, platform)

                if not items:
                    return AgentResult(
                        success=True,
                        data={"keyword": keyword, "insight": "No data available for analysis", "total_count": 0},
                    )

                # Convert ORM objects to dicts for skill processing
                items_dicts = []
                for item in items:
                    items_dicts.append({
                        "summary": item.summary or "",
                        "topics": item.topics or "",
                        "sentiment": item.sentiment or "neutral",
                        "trend_score": item.trend_score,
                        "source_platform": item.source_platform,
                        "keyword": item.keyword,
                    })

            # Resolve domain config
            domain_config = await self._resolve_domain_config(context)

            if domain_config:
                strategy = domain_config.insight_skill.strategy if hasattr(domain_config.insight_skill, 'strategy') and domain_config.insight_skill.strategy else "adaptive"
                domain_name = domain_config.display_name
                domain_description = domain_config.insight_skill.domain_description if hasattr(domain_config.insight_skill, 'domain_description') else ""
                scoring_weights = domain_config.insight_skill.scoring_weights
                decay_delta = domain_config.insight_skill.decay_delta
                anomaly_threshold_sigma = domain_config.insight_skill.anomaly_threshold_sigma
                aggregation_window_days = domain_config.insight_skill.aggregation_window_days
                report_template = domain_config.insight_skill.report_template
            else:
                strategy = "adaptive"
                domain_name = "通用"
                domain_description = ""
                scoring_weights = {"likes": 0.3, "comments": 0.4, "shares": 0.3}
                decay_delta = 0.15
                anomaly_threshold_sigma = 3.0
                aggregation_window_days = 14
                report_template = "general_trend_report"

            # Look up skill
            registry = get_registry()
            skill_cls = registry.get_skill("insight", strategy)

            if not skill_cls:
                logger.warning(f"[{self.name}] No skill registered for ('insight', '{strategy}'), falling back to 'adaptive'")
                skill_cls = registry.get_skill("insight", "adaptive")

            if not skill_cls:
                return AgentResult(success=False, error="No insight skill available")

            skill = skill_cls()
            skill_context = SkillContext(
                domain_id=context.domain_id,
                keyword=keyword,
                platform=platform or "",
                extra={"cleaned_items": items_dicts},
            )
            skill_config = {
                "domain_name": domain_name,
                "domain_description": domain_description,
                "scoring_weights": scoring_weights,
                "decay_delta": decay_delta,
                "anomaly_threshold_sigma": anomaly_threshold_sigma,
                "aggregation_window_days": aggregation_window_days,
                "report_template": report_template,
            }

            skill_result = await skill.execute(skill_context, skill_config)

            if skill_result.success:
                return AgentResult(
                    success=True,
                    data=skill_result.data,
                    skill_used=f"insight:{strategy}",
                )
            else:
                return AgentResult(success=False, error=skill_result.error, skill_used=f"insight:{strategy}")

        except Exception as e:
            logger.error(f"[{self.name}] Insight generation failed: {e}")
            return AgentResult(success=False, error=str(e))
