"""Keyword Generator — LLM-driven seed keyword generation for domain onboarding.

When a user creates a new domain, this module generates 10-20 seed keywords
using the LLM, based on the domain name and description. The keywords are
written directly to the trend_keywords table.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.infrastructure.database.models import TrendKeyword

logger = logging.getLogger(__name__)

KEYWORD_GEN_SYSTEM_TEMPLATE = """你是一个{domain_name}领域的专业关键词策划师。

你的任务是为该领域生成一组种子搜索关键词，用于社交媒体趋势监测。

领域描述：{domain_description}

生成要求：
1. 生成 {num_keywords} 个种子关键词，涵盖该领域的主要话题方向
2. 每个关键词需要包含：
   - keyword: 搜索关键词文本
   - topic_cluster: 话题簇分类（如 ingredient_technology, product_review, market_trend 等）
   - trend_type: 趋势类型（ingredient/claim/scenario/category/risk_compliance）
   - suggested_platforms: 推荐平台（xiaohongshu/douyin/bilibili/weibo 中选1-3个，用|分隔）
   - query_variants: 搜索变体词（2-3个变体，用|分隔）
3. 关键词应覆盖领域核心关注点，兼顾热度和长尾
4. 避免过于宽泛的词（如"好物推荐"），应具有领域特异性

返回JSON格式：
{{"keywords": [{{"keyword": "关键词", "topic_cluster": "话题簇", "trend_type": "趋势类型", "suggested_platforms": "platform1|platform2", "query_variants": "变体1|变体2"}}]}}"""


class KeywordGenerator:
    """Generate seed keywords for a domain using LLM."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    async def generate(
        self,
        session: AsyncSession,
        domain_id: int,
        domain_name: str,
        domain_description: str = "",
        num_keywords: int = 15,
    ) -> list[dict]:
        """Generate seed keywords for a domain and write them to the database.

        Args:
            session: AsyncSession for DB operations.
            domain_id: The domain ID to associate keywords with.
            domain_name: The domain display name.
            domain_description: Natural language description of the domain.
            num_keywords: Number of keywords to generate (default 15).

        Returns:
            List of generated keyword dicts.
        """
        system_prompt = KEYWORD_GEN_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "通用",
            domain_description=domain_description or "无特殊描述，请根据领域名称自行推断",
            num_keywords=num_keywords,
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请为{domain_name}领域生成{num_keywords}个种子搜索关键词。"},
                ],
                temperature=0.5,
                max_tokens=4000,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = self._strip_code_block(content)
            result = json.loads(content)
            keywords = result.get("keywords", [])

            if not isinstance(keywords, list):
                logger.warning(f"[KeywordGenerator] Non-list result: {type(keywords)}")
                return []

            # Write to database
            saved_keywords = []
            for idx, kw_data in enumerate(keywords):
                if not isinstance(kw_data, dict):
                    continue

                keyword_text = kw_data.get("keyword", "").strip()
                if not keyword_text:
                    continue

                # Generate a unique keyword_id
                keyword_id = f"KW_{domain_id:02d}_{idx+1:03d}"

                db_row = TrendKeyword(
                    domain_id=domain_id,
                    keyword_id=keyword_id,
                    keyword=keyword_text,
                    normalized_keyword=keyword_text.lower(),
                    topic_cluster=kw_data.get("topic_cluster", ""),
                    trend_type=kw_data.get("trend_type", "category"),
                    suggested_platforms=kw_data.get("suggested_platforms", "xiaohongshu"),
                    query_variants=kw_data.get("query_variants", ""),
                    crawl_goal="trend_discovery",
                    source_scope="llm_generated",
                    is_active=True,
                )
                session.add(db_row)
                saved_keywords.append(kw_data)

            await session.commit()
            logger.info(
                f"[KeywordGenerator] Generated and saved {len(saved_keywords)} keywords "
                f"for domain '{domain_name}' (id={domain_id})"
            )
            return saved_keywords

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[KeywordGenerator] LLM call failed: {e}")
            await session.rollback()
            return []

    async def import_csv(
        self,
        session: AsyncSession,
        domain_id: int,
        csv_content: str,
    ) -> list[dict]:
        """Import keywords from CSV content and write them to the database.

        Expected CSV columns: keyword, topic_cluster, trend_type,
        suggested_platforms, query_variants (same as trend-keyword.csv)

        Args:
            session: AsyncSession for DB operations.
            domain_id: The domain ID to associate keywords with.
            csv_content: CSV file content as string.

        Returns:
            List of imported keyword dicts.
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        saved_keywords = []
        idx = 0

        # Get max existing idx for this domain to avoid ID conflicts
        existing = await session.execute(
            select(TrendKeyword.keyword_id)
            .where(TrendKeyword.domain_id == domain_id)
            .order_by(TrendKeyword.keyword_id.desc())
            .limit(1)
        )
        existing_id = existing.scalar_one_or_none()
        idx_offset = 0
        if existing_id:
            try:
                idx_offset = int(existing_id.split("_")[-1])
            except (ValueError, IndexError):
                idx_offset = 0

        for row in reader:
            keyword_text = row.get("keyword", "").strip()
            if not keyword_text:
                continue

            idx += 1
            keyword_id = f"KW_{domain_id:02d}_{idx_offset + idx:03d}"

            db_row = TrendKeyword(
                domain_id=domain_id,
                keyword_id=keyword_id,
                keyword=keyword_text,
                normalized_keyword=keyword_text.lower(),
                topic_cluster=row.get("topic_cluster", ""),
                trend_type=row.get("trend_type", "category"),
                suggested_platforms=row.get("suggested_platforms", "xiaohongshu"),
                query_variants=row.get("query_variants", ""),
                crawl_goal=row.get("crawl_goal", "trend_discovery"),
                source_scope=row.get("source_scope", "csv_import"),
                is_active=True,
            )
            session.add(db_row)
            saved_keywords.append({
                "keyword": keyword_text,
                "keyword_id": keyword_id,
                "topic_cluster": row.get("topic_cluster", ""),
                "trend_type": row.get("trend_type", "category"),
            })

        await session.commit()
        logger.info(
            f"[KeywordGenerator] Imported {len(saved_keywords)} keywords "
            f"from CSV for domain_id={domain_id}"
        )
        return saved_keywords

    async def list_keywords(
        self,
        session: AsyncSession,
        domain_id: int,
        active_only: bool = True,
    ) -> list[dict]:
        """List keywords for a domain.

        Args:
            session: AsyncSession for DB operations.
            domain_id: The domain ID to query keywords for.
            active_only: Only return active keywords.

        Returns:
            List of keyword dicts.
        """
        stmt = select(TrendKeyword).where(TrendKeyword.domain_id == domain_id)
        if active_only:
            stmt = stmt.where(TrendKeyword.is_active == True)  # noqa: E712
        stmt = stmt.order_by(TrendKeyword.id)

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "keyword_id": row.keyword_id,
                "keyword": row.keyword,
                "topic_cluster": row.topic_cluster,
                "trend_type": row.trend_type,
                "suggested_platforms": row.suggested_platforms,
                "query_variants": row.query_variants,
                "is_active": row.is_active,
                "source_scope": row.source_scope,
                "last_crawled_at": str(row.last_crawled_at) if row.last_crawled_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def _strip_code_block(content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            first_newline = content.index("\n") + 1
            content = content[first_newline:]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].rstrip()
        return content
