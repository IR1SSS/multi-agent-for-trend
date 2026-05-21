"""Adaptive expansion skill — domain-agnostic keyword expansion via LLM inference.

Unlike hierarchical (beauty-specific levels) or tech_term (fixed 2-level structure),
this skill asks the LLM to infer the best expansion hierarchy based on the domain
description. Works for ANY domain without code changes.
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

ADAPTIVE_SYSTEM_TEMPLATE = """你是一个{domain_name}领域的专业关键词扩展专家。

你的任务是根据该领域的特点，自行设计最合适的扩展层级结构，然后按层级扩展搜索关键词。

工作步骤：
1. 先推断该领域最合理的语义层级（例如：美妆→品类/成分/痛点；汽车→车型/技术/场景；金融→产品/指标/政策）
2. 按照推断的层级结构，将原始关键词扩展为多个搜索词变体
3. 每个扩展词需要标注所属层级和父关键词

领域描述：{domain_description}

严格约束：
1. 所有扩展词必须明确指向{domain_name}领域相关内容
2. 以下关键词为负向词，绝对不能出现在扩展结果中：{negative_keywords}
3. 扩展深度不超过 {max_depth} 层
4. 推断的层级数量建议在2-4个之间

返回JSON格式：
{{"inferred_levels": ["层级1", "层级2", "层级3"], "expanded_keywords": [{{"keyword": "扩展词", "depth": 1, "parent": "原始关键词", "level": "所属层级"}}]}}"""

ADAPTIVE_USER_TEMPLATE = """原始关键词: {keyword}
主题簇: {topic_cluster}
趋势类型: {trend_type}
已有变体: {existing_variants}

请先推断该领域最合适的扩展层级，然后按层级生成搜索词变体，严格按JSON格式返回。"""


@register_skill("expander", "adaptive")
class AdaptiveExpanderSkill(BaseExpanderSkill):
    """Domain-agnostic keyword expansion that lets the LLM infer the best hierarchy."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "adaptive"

    async def expand(
        self,
        keyword: str,
        domain_name: str,
        negative_keywords: list[str],
        max_depth: int,
        extra: dict | None = None,
    ) -> list[dict]:
        extra = extra or {}
        domain_description = extra.get("domain_description", "")
        topic_cluster = extra.get("topic_cluster", "")
        trend_type = extra.get("trend_type", "")
        existing_variants = extra.get("query_variants", "")

        system_prompt = ADAPTIVE_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "通用",
            domain_description=domain_description or "无特殊描述，请根据领域名称自行推断",
            negative_keywords="、".join(negative_keywords) if negative_keywords else "无",
            max_depth=max_depth,
        )

        user_prompt = ADAPTIVE_USER_TEMPLATE.format(
            keyword=keyword,
            topic_cluster=topic_cluster or "unknown",
            trend_type=trend_type or "general",
            existing_variants=existing_variants or "[]",
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=800,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = self._strip_code_block(content)
            result = json.loads(content)

            # Extract inferred levels for feedback
            inferred_levels = result.get("inferred_levels", [])
            if inferred_levels:
                logger.info(
                    f"[AdaptiveExpander] Inferred levels for '{domain_name}': {inferred_levels}"
                )

            expanded = result.get("expanded_keywords", [])
            if not isinstance(expanded, list):
                logger.warning(f"[AdaptiveExpander] Non-list result: {type(expanded)}")
                return [{"keyword": keyword, "depth": 0, "parent": None, "level": ""}]

            # Validate and filter
            filtered = []
            for item in expanded:
                kw = item.get("keyword", "") if isinstance(item, dict) else str(item)
                if not kw:
                    continue
                if any(neg in kw for neg in negative_keywords):
                    logger.info(f"[AdaptiveExpander] Filtered out negative keyword: {kw}")
                    continue
                filtered.append({
                    "keyword": kw,
                    "depth": item.get("depth", 1) if isinstance(item, dict) else 1,
                    "parent": item.get("parent", keyword) if isinstance(item, dict) else keyword,
                    "level": item.get("level", "") if isinstance(item, dict) else "",
                })

            return filtered

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[AdaptiveExpander] LLM call failed: {e}")
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
