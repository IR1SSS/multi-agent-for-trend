"""Base insight skill — abstract interface for trend analysis strategies.

All insight skills must:
1. Accept cleaned data + domain config
2. Perform statistical analysis and anomaly detection
3. Generate domain-specific insight reports
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.skills.base import BaseSkill, SkillContext, SkillResult


class BaseInsightSkill(BaseSkill):
    """Abstract base class for insight/analytics skills."""

    @property
    def skill_type(self) -> str:
        return "insight"

    @abstractmethod
    async def analyze(
        self,
        items: list[dict[str, Any]],
        scoring_weights: dict[str, float],
        decay_delta: float,
        anomaly_threshold_sigma: float,
        aggregation_window_days: int,
        domain_description: str = "",
    ) -> dict[str, Any]:
        """Perform statistical analysis on cleaned data.

        Args:
            items: List of cleaned data items.
            scoring_weights: Engagement metric weights for trend scoring.
            decay_delta: Newton cooling decay exponent.
            anomaly_threshold_sigma: Std dev multiplier for burst detection.
            aggregation_window_days: Rolling window size.
            domain_description: Domain description for adaptive skill inference.

        Returns:
            Analysis result dict with sentiment, topics, burst signals, etc.
        """
        ...

    @abstractmethod
    async def generate_report(
        self,
        domain_name: str,
        report_template: str,
        analysis: dict[str, Any],
        domain_description: str = "",
    ) -> str:
        """Generate a domain-specific insight report.

        Args:
            domain_name: Domain display name.
            report_template: Report template identifier.
            analysis: The analysis result from analyze().
            domain_description: Domain description for adaptive skill inference.

        Returns:
            Generated report text.
        """
        ...

    async def execute(self, context: SkillContext, config: dict) -> SkillResult:
        """Default execute: analyze items and generate report."""
        items = context.extra.get("cleaned_items", [])
        if not items:
            return SkillResult(
                success=True,
                data={"insight": "No data available for analysis", "total_count": 0},
            )

        domain_description = config.get("domain_description", "")

        try:
            analysis = await self.analyze(
                items=items,
                scoring_weights=config.get("scoring_weights", {}),
                decay_delta=config.get("decay_delta", 0.15),
                anomaly_threshold_sigma=config.get("anomaly_threshold_sigma", 3.0),
                aggregation_window_days=config.get("aggregation_window_days", 14),
                domain_description=domain_description,
            )

            report = await self.generate_report(
                domain_name=config.get("domain_name", ""),
                report_template=config.get("report_template", "general_trend_report"),
                analysis=analysis,
                domain_description=domain_description,
            )

            return SkillResult(
                success=True,
                data={
                    **analysis,
                    "report": report,
                    "keyword": context.keyword,
                    "total_count": len(items),
                },
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
