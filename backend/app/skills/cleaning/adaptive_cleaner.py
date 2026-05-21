"""Adaptive cleaning skill — domain-agnostic data cleaning via LLM inference.

Unlike ontology_cleaner (which requires pre-defined required_entities),
this skill asks the LLM to infer the entity schema from the domain description.
Works for ANY domain without manual entity configuration.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import settings
from app.domain_meta.registry import register_skill
from app.skills.cleaning.base import BaseCleaningSkill

logger = logging.getLogger(__name__)

ADAPTIVE_CLEAN_SYSTEM_TEMPLATE = """你是一个专业的内容分析助手，专注于{domain_name}领域。

请对以下社交媒体内容进行分析，返回JSON格式的结果。

领域描述：{domain_description}

要求：
1. summary: 生成50-150字的内容摘要
2. entities: 根据领域描述和内容特点，自行推断该领域最应提取的关键实体字段，并结构化提取。若文本中未提及某字段，则填 null。
   推断原则：
   - 实体字段应反映该领域的核心关注点
   - 字段数量建议3-6个
   - 字段名应简洁明确（如美妆领域→成分/肤感/功效；汽车领域→车型/技术类型/价格区间）
3. sentiment: 情感分析，选择 positive/negative/neutral 之一
4. noise: 是否为广告/无关内容 (true/false)
{noise_filter_section}
待分析内容：
标题: {title}
描述: {desc}

请严格按以下JSON格式返回，不要添加其他内容：
{{"summary": "...", "entities": {{"字段1": "值1", "字段2": "值2"}}, "inferred_entity_names": ["字段1", "字段2"], "sentiment": "positive/negative/neutral", "noise": false}}"""


@register_skill("cleaning", "adaptive")
class AdaptiveCleaningSkill(BaseCleaningSkill):
    """Domain-agnostic data cleaning that lets the LLM infer entity schema."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "adaptive"

    async def generate_prompt(
        self,
        domain_name: str,
        required_entities: list[str],
        noise_filters: list[str],
        title: str,
        desc: str,
        domain_description: str = "",
    ) -> str:
        noise_section = ""
        if noise_filters:
            filter_lines = "\n".join(f"   - {f}" for f in noise_filters)
            noise_section = f"\n噪声判定规则：\n{filter_lines}"

        return ADAPTIVE_CLEAN_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "通用",
            domain_description=domain_description or "无特殊描述，请根据领域名称自行推断实体字段",
            noise_filter_section=noise_section,
            title=title[:500],
            desc=desc[:1000],
        )

    async def clean_item(
        self,
        item: dict[str, Any],
        domain_name: str,
        required_entities: list[str],
        noise_filters: list[str],
        domain_description: str = "",
    ) -> dict[str, Any] | None:
        title = item.get("title", "") or ""
        desc = item.get("desc", "") or item.get("description", "") or ""

        if not title and not desc:
            return None

        prompt = await self.generate_prompt(
            domain_name, required_entities, noise_filters, title, desc,
            domain_description=domain_description,
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0,
                max_tokens=4096,
                extra_body={"thinking": {"type": "enabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = self._strip_code_block(content)
            analysis = json.loads(content)

            # Skip noise
            if analysis.get("noise", False):
                return None

            # Extract inferred entity names for feedback
            inferred_entity_names = analysis.get("inferred_entity_names", [])
            if inferred_entity_names:
                logger.info(
                    f"[AdaptiveCleaner] Inferred entities for '{domain_name}': {inferred_entity_names}"
                )

            return {
                **item,
                "summary": analysis.get("summary", ""),
                "entities": analysis.get("entities", {}),
                "inferred_entity_names": inferred_entity_names,
                "topics": list(analysis.get("entities", {}).keys()),
                "sentiment": analysis.get("sentiment", "neutral"),
                "noise": False,
            }

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[AdaptiveCleaner] LLM analysis failed for item: {e}")
            return None

    @staticmethod
    def _strip_code_block(content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            first_newline = content.index("\n") + 1
            content = content[first_newline:]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].rstrip()
        return content
