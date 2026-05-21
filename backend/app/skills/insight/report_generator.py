"""Report generator skill — LLM-powered domain-specific report generation.

Generates tailored insight reports using domain-specific templates
and analysis data. Different industries get different report formats
and emphasis areas.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import settings
from app.domain_meta.registry import register_skill
from app.skills.base import SkillContext, SkillResult
from app.skills.insight.base import BaseInsightSkill

logger = logging.getLogger(__name__)

# Domain-specific report templates
REPORT_TEMPLATES: dict[str, str] = {
    "beauty_trend_report": "成分合规与研发趋势报告",
    "tech_maturity_report": "技术成熟度曲线与竞品动态简报",
    "market_sentiment_report": "市场舆情与消费者反馈报告",
    "general_trend_report": "通用趋势洞察报告",
}

REPORT_SYSTEM_TEMPLATE = """你是一个{domain_name}领域的专业趋势分析师。
请根据以下统计数据生成一份简洁、专业的趋势洞察报告。

报告模板类型: {report_type}
报告标题: {report_title}

要求:
1. 用数据支撑观点，不要空洞的描述
2. 突出突发信号和异常趋势
3. 给出可执行的建议
4. 语言专业但易懂"""

REPORT_USER_TEMPLATE = """领域: {domain_name}
统计数据:
{analysis_data}

请生成趋势洞察报告。"""


@register_skill("insight", "report_generator")
class ReportGeneratorSkill(BaseInsightSkill):
    """LLM-powered domain-specific report generation."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "report_generator"

    async def analyze(
        self,
        items: list[dict[str, Any]],
        scoring_weights: dict[str, float],
        decay_delta: float,
        anomaly_threshold_sigma: float,
        aggregation_window_days: int,
        domain_description: str = "",
    ) -> dict[str, Any]:
        # Delegate to StatisticsSkill for analysis
        from app.skills.insight.statistics import StatisticsSkill
        stats_skill = StatisticsSkill()
        return await stats_skill.analyze(
            items=items,
            scoring_weights=scoring_weights,
            decay_delta=decay_delta,
            anomaly_threshold_sigma=anomaly_threshold_sigma,
            aggregation_window_days=aggregation_window_days,
            domain_description=domain_description,
        )

    async def generate_report(
        self,
        domain_name: str,
        report_template: str,
        analysis: dict[str, Any],
        domain_description: str = "",
    ) -> str:
        report_title = REPORT_TEMPLATES.get(report_template, "通用趋势洞察报告")

        system_prompt = REPORT_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "通用",
            report_type=report_template,
            report_title=report_title,
        )

        user_prompt = REPORT_USER_TEMPLATE.format(
            domain_name=domain_name or "通用",
            analysis_data=json.dumps(analysis, ensure_ascii=False, indent=2)[:3000],
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"[ReportGenerator] LLM report generation failed: {e}")
            # Fallback to basic statistical report
            from app.skills.insight.statistics import StatisticsSkill
            stats = StatisticsSkill()
            return await stats.generate_report(domain_name, report_template, analysis, domain_description=domain_description)
