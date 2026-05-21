"""Hierarchical expansion skill — "品类-成分-痛点" three-level expansion.

Default strategy for mature industries (beauty, personal care, etc.).
Uses LLM to expand keywords through semantic hierarchy levels,
with negative keyword injection as hard constraints.
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.config.settings import settings
from app.domain_meta.registry import register_skill
from app.skills.base import SkillContext, SkillResult
from app.skills.expander.base import BaseExpanderSkill

logger = logging.getLogger(__name__)

HIERARCHICAL_SYSTEM_TEMPLATE = """你是一个专门为{domain_name}领域社交媒体爬虫服务的关键词扩充专家。

你的任务是根据语义层级扩展搜索关键词。扩展层级为：{levels}

严格约束：
1. 所有扩展词必须明确指向{domain_name}领域相关内容
2. 以下关键词为负向词，绝对不能出现在扩展结果中：{negative_keywords}
3. 扩展深度不超过 {max_depth} 层
4. 每个扩展词需要记录其父关键词和深度层级

返回JSON格式：
{{"expanded_keywords": [{{"keyword": "扩展词", "depth": 1, "parent": "原始关键词"}}]}}"""

HIERARCHICAL_USER_TEMPLATE = """原始关键词: {keyword}
主题簇: {topic_cluster}
趋势类型: {trend_type}
已有变体: {existing_variants}

请按{levels}层级生成扩充后的搜索词，严格按JSON格式返回。"""


@register_skill("expander", "hierarchical")
class HierarchicalExpanderSkill(BaseExpanderSkill):
    """Three-level hierarchical keyword expansion for mature industries."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "hierarchical"

    async def expand(
        self,
        keyword: str,
        domain_name: str,
        negative_keywords: list[str],
        max_depth: int,
        extra: dict | None = None,
    ) -> list[dict]:
        extra = extra or {}
        levels = extra.get("levels", ["品类", "成分", "痛点"])
        topic_cluster = extra.get("topic_cluster", "")
        trend_type = extra.get("trend_type", "ingredient")
        existing_variants = extra.get("query_variants", "")

        system_prompt = HIERARCHICAL_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "美妆护肤",
            levels=" → ".join(levels),
            negative_keywords="、".join(negative_keywords) if negative_keywords else "无",
            max_depth=max_depth,
        )

        user_prompt = HIERARCHICAL_USER_TEMPLATE.format(
            keyword=keyword,
            topic_cluster=topic_cluster or "unknown",
            trend_type=trend_type,
            existing_variants=existing_variants or "[]",
            levels=" → ".join(levels),
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = self._strip_code_block(content)
            result = json.loads(content)
            expanded = result.get("expanded_keywords", [])

            if not isinstance(expanded, list):
                logger.warning(f"[HierarchicalExpander] Non-list result: {type(expanded)}")
                return [{"keyword": keyword, "depth": 0, "parent": None}]

            # Validate negative keywords are not in results
            filtered = []
            for item in expanded:
                kw = item.get("keyword", "") if isinstance(item, dict) else str(item)
                if any(neg in kw for neg in negative_keywords):
                    logger.info(f"[HierarchicalExpander] Filtered out negative keyword: {kw}")
                    continue
                filtered.append({
                    "keyword": kw,
                    "depth": item.get("depth", 1) if isinstance(item, dict) else 1,
                    "parent": item.get("parent", keyword) if isinstance(item, dict) else keyword,
                })

            return filtered

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[HierarchicalExpander] LLM call failed: {e}")
            return []

    @staticmethod
    def _strip_code_block(content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            first_newline = content.index("\n") + 1
            content = content[first_newline:]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].rstrip()
        return content
