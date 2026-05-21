"""Adaptive insight skill — domain-agnostic trend analysis via LLM inference.

Unlike statistics (pure numerical) or report_generator (template-based),
this skill uses the LLM to infer the best analysis framework and report
format based on the domain description. Works for ANY domain.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import settings
from app.domain_meta.registry import register_skill
from app.skills.insight.base import BaseInsightSkill

logger = logging.getLogger(__name__)

ADAPTIVE_INSIGHT_SYSTEM_TEMPLATE = """你是一个{domain_name}领域的专业趋势分析师。

你的任务是对该领域的社交媒体趋势数据进行分析，并生成洞察报告。

领域描述：{domain_description}

分析要求：
1. sentiment_summary: 整体情感倾向分析（正面/负面/中性的分布与原因）
2. topic_analysis: 核心话题分析（提取高频话题、话题关联、新兴话题）
3. burst_signals: 爆发信号检测（识别异常热度的话题及其可能原因）
4. key_insights: 3-5条关键洞察（每条洞察应有数据支撑）
5. recommendations: 基于分析的行动建议

返回JSON格式：
{{"sentiment_summary": "情感分析摘要", "topic_analysis": {{"hot_topics": ["话题1"], "emerging_topics": ["新话题1"], "topic_connections": "话题关联描述"}}, "burst_signals": [{{"topic": "话题", "signal": "信号描述"}}], "key_insights": ["洞察1", "洞察2"], "recommendations": ["建议1", "建议2"]}}"""


@register_skill("insight", "adaptive")
class AdaptiveInsightSkill(BaseInsightSkill):
    """Domain-agnostic insight analysis that lets the LLM infer the analysis framework."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "adaptive"

    async def analyze(
        self,
        items: list[dict[str, Any]],
        scoring_weights: dict[str, float],
        decay_delta: float,
        anomaly_threshold_sigma: float,
        aggregation_window_days: int,
        domain_description: str = "",
    ) -> dict[str, Any]:
        """Perform basic statistical pre-analysis on cleaned data."""
        if not items:
            return {"total_count": 0, "sentiment_distribution": {}, "avg_trend_score": 0.0}

        # Statistical pre-processing (no LLM needed)
        sentiment_counts: dict[str, int] = {}
        total_score = 0.0
        topic_counts: dict[str, int] = {}

        for item in items:
            s = item.get("sentiment", "neutral")
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
            total_score += float(item.get("trend_score", 0))

            topics_str = item.get("topics", "")
            if topics_str:
                for t in topics_str.split(","):
                    t = t.strip()
                    if t:
                        topic_counts[t] = topic_counts.get(t, 0) + 1

        avg_score = total_score / len(items) if items else 0.0
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_count": len(items),
            "sentiment_distribution": sentiment_counts,
            "avg_trend_score": round(avg_score, 2),
            "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
            "domain_description": domain_description,
        }

    async def generate_report(
        self,
        domain_name: str,
        report_template: str,
        analysis: dict[str, Any],
        domain_description: str = "",
    ) -> str:
        """Generate an insight report using LLM with domain context."""
        system_prompt = ADAPTIVE_INSIGHT_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "通用",
            domain_description=domain_description or "无特殊描述，请根据领域名称自行推断分析框架",
        )

        user_prompt = f"""以下是对{domain_name}领域的趋势数据分析结果，请生成洞察报告：

数据统计：
- 总数据量: {analysis.get('total_count', 0)} 条
- 平均趋势分: {analysis.get('avg_trend_score', 0)}
- 情感分布: {json.dumps(analysis.get('sentiment_distribution', {}), ensure_ascii=False)}
- 热门话题: {json.dumps(analysis.get('top_topics', [])[:5], ensure_ascii=False)}

请基于以上数据进行深度分析，严格按JSON格式返回。"""

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=2000,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = self._strip_code_block(content)
            result = json.loads(content)

            # Format as readable report
            report_parts = [
                f"# {domain_name}趋势洞察报告\n",
                f"## 情感分析\n{result.get('sentiment_summary', 'N/A')}\n",
                f"## 话题分析\n",
            ]

            ta = result.get("topic_analysis", {})
            if isinstance(ta, dict):
                hot = ", ".join(ta.get("hot_topics", []))
                emerging = ", ".join(ta.get("emerging_topics", []))
                report_parts.append(f"- 热门话题: {hot}")
                report_parts.append(f"- 新兴话题: {emerging}")
                report_parts.append(f"- 话题关联: {ta.get('topic_connections', 'N/A')}")

            burst_signals = result.get("burst_signals", [])
            if burst_signals:
                report_parts.append("\n## 爆发信号")
                for sig in burst_signals:
                    if isinstance(sig, dict):
                        report_parts.append(f"- **{sig.get('topic', 'N/A')}**: {sig.get('signal', 'N/A')}")

            insights = result.get("key_insights", [])
            if insights:
                report_parts.append("\n## 关键洞察")
                for i, ins in enumerate(insights, 1):
                    report_parts.append(f"{i}. {ins}")

            recs = result.get("recommendations", [])
            if recs:
                report_parts.append("\n## 行动建议")
                for i, rec in enumerate(recs, 1):
                    report_parts.append(f"{i}. {rec}")

            return "\n".join(report_parts)

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[AdaptiveInsight] LLM call failed: {e}")
            return f"# {domain_name}趋势洞察报告\n\n基础统计：共{analysis.get('total_count', 0)}条数据，平均趋势分{analysis.get('avg_trend_score', 0)}"

    @staticmethod
    def _strip_code_block(content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            first_newline = content.index("\n") + 1
            content = content[first_newline:]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].rstrip()
        return content
