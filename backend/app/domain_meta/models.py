"""Domain configuration Pydantic models.

These models define the shape of a domain's metadata, including the
three core skill configurations (expander, cleaning, insight).
Crawler platform selection is handled by the user at pipeline start time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Skill sub-configurations ────────────────────────────────────────────


class ExpanderSkillConfig(BaseModel):
    """Configuration for the keyword expansion skill."""

    strategy: str = Field(
        default="adaptive",
        description="Expansion strategy: 'adaptive' (auto-infer), 'hierarchical' (mature industries) or 'tech_term' (emerging industries)",
    )
    negative_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to exclude from expansion results (e.g. ['二手车', '车模'] for new_energy_vehicle)",
    )
    max_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum expansion depth for the keyword tree",
    )
    levels: list[str] = Field(
        default_factory=list,
        description="Semantic levels for hierarchical expansion (auto-inferred when using 'adaptive' strategy)",
    )
    domain_description: str = Field(
        default="",
        description="Domain description text for adaptive skill to infer expansion levels",
    )


class CleaningSkillConfig(BaseModel):
    """Configuration for the data cleaning skill."""

    strategy: str = Field(
        default="adaptive",
        description="Cleaning strategy: 'adaptive' (auto-infer entities) or 'ontology_cleaner' (pre-defined entities)",
    )
    required_entities: list[str] = Field(
        default_factory=list,
        description="Entity types to extract (auto-inferred when using 'adaptive' strategy)",
    )
    noise_filters: list[str] = Field(
        default_factory=list,
        description="Noise filter rules for LLM-as-a-Judge",
    )
    domain_description: str = Field(
        default="",
        description="Domain description text for adaptive skill to infer entity schema",
    )
    eval_metrics: list[str] = Field(
        default_factory=lambda: ["schema_alignment", "factuality"],
        description="Evaluation metrics for the quality gate",
    )
    judge_enabled: bool = Field(
        default=True,
        description="Whether to enable the LLM-as-a-Judge quality gate",
    )
    judge_model: str = Field(
        default="gpt-4o-mini",
        description="Model to use for the judge (should be small and fast)",
    )
    max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Max retries when judge rejects a cleaned result",
    )


class InsightSkillConfig(BaseModel):
    """Configuration for the insight/analytics skill."""

    strategy: str = Field(
        default="adaptive",
        description="Insight strategy: 'adaptive' (auto-infer report format), 'statistics' or 'report_generator'",
    )
    scoring_weights: dict[str, float] = Field(
        default_factory=lambda: {"likes": 0.3, "comments": 0.4, "shares": 0.3},
        description="Engagement metric weights for trend score calculation",
    )
    anomaly_threshold_sigma: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        description="Number of standard deviations for burst signal detection",
    )
    aggregation_window_days: int = Field(
        default=14,
        ge=1,
        le=90,
        description="Rolling window size (days) for anomaly detection",
    )
    decay_delta: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Newton cooling decay exponent (higher = faster decay for fast-moving industries)",
    )
    report_template: str = Field(
        default="general_trend_report",
        description="Report template identifier for this domain",
    )
    domain_description: str = Field(
        default="",
        description="Domain description text for adaptive skill to infer report format",
    )


# ── Full Domain Configuration ───────────────────────────────────────────


class DomainConfigCreate(BaseModel):
    """Request schema for creating a new domain configuration."""

    domain: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$", description="Unique domain identifier, e.g. 'beauty', 'new_energy_vehicle'")
    display_name: str = Field(..., min_length=1, max_length=128, description="Human-readable domain name, e.g. '美妆护肤'")
    domain_description: str = Field(
        default="",
        description="Natural language description of the domain for LLM-based skill inference",
    )
    status: str = Field(default="active", pattern=r"^(active|archived)$")
    expander_skill: ExpanderSkillConfig = Field(default_factory=ExpanderSkillConfig)
    cleaning_skill: CleaningSkillConfig = Field(default_factory=CleaningSkillConfig)
    insight_skill: InsightSkillConfig = Field(default_factory=InsightSkillConfig)


class DomainConfigUpdate(BaseModel):
    """Request schema for updating a domain configuration."""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    domain_description: Optional[str] = Field(default=None, description="Updated domain description for LLM-based skill inference")
    status: Optional[str] = Field(default=None, pattern=r"^(active|archived)$")
    expander_skill: Optional[ExpanderSkillConfig] = None
    cleaning_skill: Optional[CleaningSkillConfig] = None
    insight_skill: Optional[InsightSkillConfig] = None


class DomainConfigRead(BaseModel):
    """Response schema for reading a domain configuration."""

    id: int
    domain: str
    display_name: str
    domain_description: str = ""
    status: str
    expander_skill: dict
    cleaning_skill: dict
    insight_skill: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Resolved Domain Configuration (after parsing + validation) ──────────


class ResolvedDomainConfig(BaseModel):
    """Strongly-typed domain configuration after parsing and default-filling.

    This is what the DomainConfigParser produces — all fields are guaranteed
    to be present and correctly typed.
    """

    id: int
    domain: str
    display_name: str
    domain_description: str = ""
    status: str
    expander_skill: ExpanderSkillConfig
    cleaning_skill: CleaningSkillConfig
    insight_skill: InsightSkillConfig

    @classmethod
    def from_domain_config_read(cls, read: DomainConfigRead) -> ResolvedDomainConfig:
        """Create a ResolvedDomainConfig from a DomainConfigRead (DB row)."""
        return cls(
            id=read.id,
            domain=read.domain,
            display_name=read.display_name,
            domain_description=read.domain_description,
            status=read.status,
            expander_skill=ExpanderSkillConfig(**read.expander_skill),
            cleaning_skill=CleaningSkillConfig(**read.cleaning_skill),
            insight_skill=InsightSkillConfig(**read.insight_skill),
        )
