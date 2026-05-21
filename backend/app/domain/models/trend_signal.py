from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrendSignalRead(BaseModel):
    """First-party trend_signal schema for downstream QA consumption."""

    signal_id: str
    keyword_id: str
    crawl_task_id: int
    normalized_keyword: str
    topic_cluster: str
    trend_type: str
    signal_summary: str
    signal_evidence: str
    source_platform: str
    source_url: str
    trend_score: float
    confidence: str = Field(pattern=r"^(low|medium|high)$")
    risk_flag: str = Field(pattern=r"^(low|medium|high)$")
    observed_at: str
    fresh_until: str

    report_id: str | None = None
    signal_period_type: str | None = None
    signal_period_label: str | None = None
    source_scope: str | None = None
    support_count: int = 1
    evidence_ids: list[str] = Field(default_factory=list)
    aggregation_method: str = "record_level_v0"
    version: str = "v0.1"


class TrendSignalQuery(BaseModel):
    """Query parameters for searching trend_signal records."""

    normalized_keyword: str | None = None
    topic_cluster: str | None = None
    trend_type: str | None = Field(default=None, pattern=r"^(ingredient|claim|scenario|category|risk_compliance)$")
    source_platform: str | None = None
    risk_flag: str | None = Field(default=None, pattern=r"^(low|medium|high)$")
    min_confidence: str | None = Field(default=None, pattern=r"^(low|medium|high)$")
    min_trend_score: float | None = Field(default=None, ge=0.0)
    fresh_only: bool = True
    freshness_days: int = Field(default=7, ge=1, le=30)
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class TrendSignalExport(BaseModel):
    """Export envelope for trend_signal outputs."""

    normalized_keyword: str
    source_platform: str
    generated_at: datetime
    results: list[TrendSignalRead]
