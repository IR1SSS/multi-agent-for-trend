"""Base expander skill — abstract interface for keyword expansion strategies.

All expander skills must:
1. Accept a seed keyword + domain config
2. Return expanded keywords with parent-child depth tracking
3. Inject negative_keywords as LLM constraints
"""
from __future__ import annotations

from abc import abstractmethod

from app.skills.base import BaseSkill, SkillContext, SkillResult


class BaseExpanderSkill(BaseSkill):
    """Abstract base class for keyword expansion skills."""

    @property
    def skill_type(self) -> str:
        return "expander"

    @abstractmethod
    async def expand(
        self,
        keyword: str,
        domain_name: str,
        negative_keywords: list[str],
        max_depth: int,
        extra: dict | None = None,
    ) -> list[dict]:
        """Expand a keyword into search variants.

        Args:
            keyword: The seed keyword to expand.
            domain_name: The domain display name for prompt context.
            negative_keywords: Keywords to exclude from results.
            max_depth: Maximum expansion depth.
            extra: Additional context (e.g. topic_cluster, trend_type).

        Returns:
            List of dicts: [{"keyword": str, "depth": int, "parent": str | None}]
        """
        ...

    async def execute(self, context: SkillContext, config: dict) -> SkillResult:
        """Default execute implementation that delegates to expand()."""
        try:
            expanded = await self.expand(
                keyword=context.keyword,
                domain_name=config.get("domain_name", ""),
                negative_keywords=config.get("negative_keywords", []),
                max_depth=config.get("max_depth", 2),
                extra=context.extra,
            )

            # Build merged keyword list (original + expanded, deduped, max 3)
            MAX_CRAWL_KEYWORDS = 3
            merged = [context.keyword]
            for item in expanded:
                kw = item["keyword"]
                if kw not in merged:
                    merged.append(kw)
                if len(merged) >= MAX_CRAWL_KEYWORDS:
                    break

            return SkillResult(
                success=True,
                data={
                    "original_keyword": context.keyword,
                    "expanded_keywords": [item["keyword"] for item in expanded],
                    "keyword_tree": expanded,
                    "merged_keywords": merged,
                    "keywords_for_crawler": ",".join(merged),
                },
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
