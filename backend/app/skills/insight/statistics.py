"""Statistical analysis skill — pure math module for trend analysis.

Implements:
- Newton cooling decay for time-weighted trend scores
- 3-sigma / rolling Z-Score anomaly detection
- BURST_SIGNAL detection
No business logic dependency — purely mathematical.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from app.domain_meta.registry import register_skill
from app.skills.base import SkillContext, SkillResult
from app.skills.insight.base import BaseInsightSkill

logger = logging.getLogger(__name__)


def newton_cooling_score(
    current_score: float,
    days_since_event: float,
    delta: float = 0.15,
) -> float:
    """Apply Newton cooling decay to a trend score.

    score(t) = score_0 * e^(-delta * t)

    Args:
        current_score: The raw engagement-based score.
        days_since_event: Days since the content was published.
        delta: Decay exponent (higher = faster decay for fast-moving industries).

    Returns:
        Decay-adjusted score.
    """
    return current_score * math.exp(-delta * days_since_event)


def rolling_z_score(
    current_value: float,
    historical_values: list[float],
    threshold_sigma: float = 3.0,
) -> dict[str, Any]:
    """Compute rolling Z-Score for burst signal detection.

    Args:
        current_value: Today's metric value (e.g. interaction count).
        historical_values: Historical values for the rolling window.
        threshold_sigma: Number of standard deviations for burst threshold.

    Returns:
        Dict with z_score, is_burst, mean, std_dev, threshold.
    """
    if not historical_values:
        return {
            "z_score": 0.0,
            "is_burst": False,
            "mean": 0.0,
            "std_dev": 0.0,
            "threshold": threshold_sigma,
        }

    mean = sum(historical_values) / len(historical_values)
    variance = sum((x - mean) ** 2 for x in historical_values) / len(historical_values)
    std_dev = math.sqrt(variance) if variance > 0 else 0.001

    z_score = (current_value - mean) / std_dev if std_dev > 0 else 0.0
    is_burst = abs(z_score) > threshold_sigma

    return {
        "z_score": round(z_score, 4),
        "is_burst": is_burst,
        "mean": round(mean, 2),
        "std_dev": round(std_dev, 4),
        "threshold": threshold_sigma,
    }


def compute_weighted_trend_score(
    likes: int,
    comments: int,
    shares: int,
    collected: int,
    weights: dict[str, float] | None = None,
    days_since: float = 0.0,
    delta: float = 0.15,
) -> float:
    """Compute a weighted, decay-adjusted trend score.

    Args:
        likes: Like count.
        comments: Comment count.
        shares: Share count.
        collected: Collect/save count.
        weights: Per-metric weights from domain config.
        days_since: Days since publication (for decay).
        delta: Decay exponent.

    Returns:
        Decay-adjusted weighted trend score.
    """
    w = weights or {"likes": 0.3, "comments": 0.4, "shares": 0.3}
    raw_score = (
        likes * w.get("likes", 0.3)
        + comments * w.get("comments", 0.4)
        + shares * w.get("shares", 0.3)
        + collected * w.get("collected", 0.2)
    )
    return newton_cooling_score(raw_score, days_since, delta)


@register_skill("insight", "statistics")
class StatisticsSkill(BaseInsightSkill):
    """Pure mathematical statistical analysis for trend insights."""

    @property
    def strategy_name(self) -> str:
        return "statistics"

    async def analyze(
        self,
        items: list[dict[str, Any]],
        scoring_weights: dict[str, float],
        decay_delta: float,
        anomaly_threshold_sigma: float,
        aggregation_window_days: int,
        domain_description: str = "",
    ) -> dict[str, Any]:
        if not items:
            return {"total_count": 0, "analysis": {}}

        # Aggregate metrics
        sentiment_counts: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0}
        topic_counts: dict[str, int] = {}
        daily_scores: dict[str, list[float]] = {}
        total_score = 0.0

        for item in items:
            # Sentiment aggregation
            sentiment = item.get("sentiment", "neutral")
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

            # Topic aggregation
            topics = item.get("topics", "")
            if isinstance(topics, str):
                for topic in topics.split(","):
                    topic = topic.strip()
                    if topic:
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1
            elif isinstance(topics, list):
                for topic in topics:
                    topic_counts[str(topic)] = topic_counts.get(str(topic), 0) + 1

            # Compute weighted trend score
            likes = self._safe_int(item.get("liked_count", 0))
            comments = self._safe_int(item.get("comment_count", 0))
            shares = self._safe_int(item.get("share_count", 0))
            collected = self._safe_int(item.get("collected_count", 0))

            score = compute_weighted_trend_score(
                likes=likes,
                comments=comments,
                shares=shares,
                collected=collected,
                weights=scoring_weights,
                days_since=0.0,  # Would need publish_time for real decay
                delta=decay_delta,
            )
            total_score += score

            # Group by date for anomaly detection
            date_key = item.get("date", "unknown")
            if date_key not in daily_scores:
                daily_scores[date_key] = []
            daily_scores[date_key].append(score)

        avg_score = total_score / len(items) if items else 0
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Burst signal detection per keyword
        burst_signals = []
        score_values = [total_score / len(items)] if items else [0.0]
        # Use daily total scores for anomaly detection
        daily_totals = [sum(scores) for scores in daily_scores.values()]
        if daily_totals and len(daily_totals) >= 2:
            latest = daily_totals[-1]
            historical = daily_totals[:-1]
            z_result = rolling_z_score(latest, historical, anomaly_threshold_sigma)
            if z_result["is_burst"]:
                burst_signals.append({
                    "type": "BURST_SIGNAL",
                    "z_score": z_result["z_score"],
                    "threshold": anomaly_threshold_sigma,
                    "metric": "daily_interaction_score",
                })

        return {
            "total_count": len(items),
            "analyzed_count": len(items),
            "avg_trend_score": round(avg_score, 2),
            "total_trend_score": round(total_score, 2),
            "sentiment_distribution": sentiment_counts,
            "top_topics": top_topics,
            "burst_signals": burst_signals,
            "scoring_weights": scoring_weights,
            "decay_delta": decay_delta,
        }

    async def generate_report(
        self,
        domain_name: str,
        report_template: str,
        analysis: dict[str, Any],
        domain_description: str = "",
    ) -> str:
        """Generate a basic statistical summary report.

        Full LLM-powered report generation is in ReportGeneratorSkill.
        """
        sentiment = analysis.get("sentiment_distribution", {})
        top_topics = analysis.get("top_topics", [])
        burst_signals = analysis.get("burst_signals", [])

        lines = [
            f"# {domain_name} 趋势洞察报告",
            f"",
            f"## 总览",
            f"- 分析条目数: {analysis.get('total_count', 0)}",
            f"- 平均趋势分: {analysis.get('avg_trend_score', 0):.2f}",
            f"- 衰减指数 δ: {analysis.get('decay_delta', 0.15)}",
            f"",
            f"## 情感分布",
        ]
        for s, count in sentiment.items():
            lines.append(f"- {s}: {count}")

        if top_topics:
            lines.append(f"\n## 热门主题 (Top 10)")
            for topic, count in top_topics:
                lines.append(f"- {topic}: {count}")

        if burst_signals:
            lines.append(f"\n## 突发信号")
            for signal in burst_signals:
                lines.append(f"- **{signal['type']}**: Z-Score={signal['z_score']:.2f} (阈值={signal['threshold']})")

        return "\n".join(lines)

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0
