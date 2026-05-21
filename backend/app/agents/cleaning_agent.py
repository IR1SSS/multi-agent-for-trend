from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.config.settings import settings
from app.domain_meta.registry import get_registry
from app.infrastructure.database.connection import async_session_factory
from app.infrastructure.database.models import CleanedTrendData
from app.infrastructure.repositories.trend_repo_impl import TrendRepositoryImpl
from app.skills.base import SkillContext

logger = logging.getLogger(__name__)

# SQL to fetch raw data from MediaCrawler tables after a crawl
RAW_DATA_QUERIES = {
    "xhs": "SELECT note_id as source_id, title, \"desc\", 'note' as source_type, liked_count, collected_count, comment_count, share_count, source_keyword FROM xhs_note WHERE source_keyword = :keyword AND time >= :time_threshold",
    "dy": "SELECT aweme_id as source_id, title, \"desc\", 'video' as source_type, liked_count, '' as collected_count, comment_count, share_count, source_keyword FROM douyin_aweme WHERE source_keyword = :keyword AND create_time >= :time_threshold",
    "bili": "SELECT video_id as source_id, title, \"desc\" as description, 'video' as source_type, liked_count, video_favorite_count as collected_count, video_comment as comment_count, video_share_count as share_count, source_keyword FROM bilibili_video WHERE source_keyword = :keyword AND created_at >= :time_threshold_str",
    "wb": "SELECT note_id as source_id, '' as title, content as \"desc\", 'note' as source_type, liked_count, '' as collected_count, comments_count as comment_count, shared_count as share_count, source_keyword FROM weibo_note WHERE source_keyword = :keyword",
}


class CleaningAgent(BaseAgent):
    """Agent responsible for AI-powered data cleaning of crawled content.

    Delegates to the domain-configured CleaningSkill (e.g. 'ontology_cleaner')
    for prompt generation and entity extraction. Optionally applies the
    LLM-as-a-Judge quality gate for validation.
    """

    @property
    def name(self) -> str:
        return "CleaningAgent"

    async def execute(self, context: AgentContext) -> AgentResult:
        """Clean raw data for a completed crawl task.

        Expects context to have:
        - task_id: The completed crawl task ID
        - platform: The platform that was crawled
        - keyword: The keyword that was used
        - domain_id: The domain configuration ID
        """
        task_id = context.task_id
        platform = context.platform
        keyword = context.keyword

        if not task_id or not platform or not keyword:
            return AgentResult(success=False, error="Missing task_id, platform, or keyword")

        try:
            # Step 1: Read raw data from MediaCrawler tables
            raw_items = await self._fetch_raw_data(platform, keyword)

            if not raw_items:
                logger.info(f"[{self.name}] No raw data found for {platform}/{keyword}")
                return AgentResult(success=True, data={"cleaned_count": 0})

            # Step 2: Resolve domain config for skill lookup
            domain_config = await self._resolve_domain_config(context)

            if domain_config:
                strategy = domain_config.cleaning_skill.strategy if hasattr(domain_config.cleaning_skill, 'strategy') and domain_config.cleaning_skill.strategy else "adaptive"
                domain_name = domain_config.display_name
                required_entities = domain_config.cleaning_skill.required_entities
                noise_filters = domain_config.cleaning_skill.negative_keywords if hasattr(domain_config.cleaning_skill, 'negative_keywords') else domain_config.cleaning_skill.noise_filters
                domain_description = domain_config.cleaning_skill.domain_description if hasattr(domain_config.cleaning_skill, 'domain_description') else ""
                judge_enabled = domain_config.cleaning_skill.judge_enabled
                judge_model = domain_config.cleaning_skill.judge_model
            else:
                strategy = "adaptive"
                domain_name = "通用"
                required_entities = []
                noise_filters = []
                domain_description = ""
                judge_enabled = True
                judge_model = settings.LLM_JUDGE_MODEL

            # Step 3: Execute cleaning skill
            registry = get_registry()
            skill_cls = registry.get_skill("cleaning", strategy)

            if not skill_cls:
                logger.error(f"[{self.name}] No cleaning skill for strategy '{strategy}'")
                return AgentResult(success=False, error=f"No cleaning skill: {strategy}")

            skill = skill_cls()
            skill_context = SkillContext(
                domain_id=context.domain_id,
                task_id=task_id,
                keyword=keyword,
                platform=platform,
                extra={"raw_items": raw_items},
            )
            skill_config = {
                "domain_name": domain_name,
                "required_entities": required_entities,
                "noise_filters": noise_filters,
                "domain_description": domain_description,
            }

            skill_result = await skill.execute(skill_context, skill_config)

            if not skill_result.success:
                return AgentResult(success=False, error=skill_result.error, skill_used=f"cleaning:{strategy}")

            cleaned_items_raw = skill_result.data.get("cleaned_items", [])

            # Step 4: Optional LLM Judge quality gate
            if judge_enabled and cleaned_items_raw:
                judge_cls = registry.get_skill("cleaning", "judge")
                if judge_cls:
                    judge = judge_cls()
                    judge_context = SkillContext(
                        domain_id=context.domain_id,
                        extra={"items_to_judge": cleaned_items_raw},
                    )
                    judge_config = {
                        "domain_name": domain_name,
                        "required_entities": required_entities,
                        "judge_model": judge_model,
                    }
                    judge_result = await judge.execute(judge_context, judge_config)
                    if judge_result.success:
                        cleaned_items_raw = judge_result.data.get("passed_items", cleaned_items_raw)

            # Step 5: Convert to CleanedTrendData and save
            cleaned_items = []
            for item in cleaned_items_raw:
                cleaned = self._to_cleaned_trend_data(item, platform, keyword, task_id)
                if cleaned:
                    cleaned_items.append(cleaned)

            async with async_session_factory() as session:
                repo = TrendRepositoryImpl(session)
                if cleaned_items:
                    await repo.bulk_create(cleaned_items)
                    await session.commit()

            # Save to local JSON
            if cleaned_items:
                self._save_to_local_json(cleaned_items, platform, keyword, task_id)

            logger.info(f"[{self.name}] Cleaned {len(cleaned_items)} items for task {task_id}")
            return AgentResult(
                success=True,
                data={"cleaned_count": len(cleaned_items), "task_id": task_id},
                skill_used=f"cleaning:{strategy}",
            )

        except Exception as e:
            logger.error(f"[{self.name}] Cleaning failed for task {task_id}: {e}")
            return AgentResult(success=False, error=str(e))

    async def _fetch_raw_data(self, platform: str, keyword: str) -> list[dict]:
        """Fetch raw data from MediaCrawler tables."""
        query = RAW_DATA_QUERIES.get(platform)
        if not query:
            logger.warning(f"[{self.name}] No raw data query for platform: {platform}")
            return []

        from datetime import timedelta
        twelve_months_ago = datetime.now() - timedelta(days=365)
        time_threshold_ms = int(twelve_months_ago.timestamp() * 1000)
        time_threshold_str = twelve_months_ago.strftime("%Y-%m-%d")

        from sqlalchemy import text
        async with async_session_factory() as session:
            result = await session.execute(
                text(query),
                {"keyword": keyword, "time_threshold": time_threshold_ms, "time_threshold_str": time_threshold_str},
            )
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    @staticmethod
    def _to_cleaned_trend_data(item: dict, platform: str, keyword: str, task_id: int) -> Optional[CleanedTrendData]:
        """Convert a cleaned item dict to a CleanedTrendData ORM object."""
        title = item.get("title", "") or ""
        summary = item.get("summary", "") or ""
        topics = item.get("topics", "") or ""
        if isinstance(topics, list):
            topics = ",".join(str(t) for t in topics)
        sentiment = item.get("sentiment", "neutral") or "neutral"

        # Calculate trend score
        liked = CleaningAgent._safe_int(item.get("liked_count", 0))
        collected = CleaningAgent._safe_int(item.get("collected_count", 0))
        comment = CleaningAgent._safe_int(item.get("comment_count", 0))
        share = CleaningAgent._safe_int(item.get("share_count", 0))
        trend_score = liked * 1.0 + collected * 2.0 + comment * 1.5 + share * 3.0

        return CleanedTrendData(
            source_type=item.get("source_type", "note"),
            source_id=str(item.get("source_id", "")),
            source_platform=platform,
            keyword=keyword,
            crawl_task_id=task_id,
            title=title[:500],
            summary=summary,
            topics=topics,
            sentiment=sentiment,
            trend_score=min(trend_score, 10000.0),
            raw_data=item,
        )

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _save_to_local_json(
        cleaned_items: list[CleanedTrendData],
        platform: str,
        keyword: str,
        task_id: int,
    ) -> Path:
        import json as _json
        base_dir = Path(settings.DATA_DIR) / "cleaned" / platform
        base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = keyword.replace(" ", "_").replace("/", "_")
        filename = f"{safe_keyword}_task{task_id}_{timestamp}.json"
        filepath = base_dir / filename

        records = []
        for item in cleaned_items:
            records.append({
                "source_type": item.source_type,
                "source_id": item.source_id,
                "source_platform": item.source_platform,
                "keyword": item.keyword,
                "crawl_task_id": item.crawl_task_id,
                "title": item.title,
                "summary": item.summary,
                "topics": item.topics,
                "sentiment": item.sentiment,
                "trend_score": item.trend_score,
                "raw_data": item.raw_data,
            })

        output = {
            "metadata": {"platform": platform, "keyword": keyword, "task_id": task_id, "cleaned_count": len(records), "generated_at": datetime.now().isoformat()},
            "data": records,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            _json.dump(output, f, ensure_ascii=False, indent=2)

        return filepath
