"""Ontology-driven cleaning skill — dynamic prompt generation based on domain entities.

Generates cleaning prompts from domain_config's required_entities instead of
hardcoded beauty-specific fields. Supports any domain's ontology.
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

ONTOLOGY_PROMPT_TEMPLATE = """你是一个专业的内容分析助手。请对以下{domain_name}领域社交媒体内容进行分析，返回JSON格式的结果。

要求：
1. summary: 生成50-150字的内容摘要
2. entities: 根据当前[{domain_name}]行业的实体定义，结构化提取以下字段：{required_entities}。若文本中未提及某字段，则填 null。
3. sentiment: 情感分析，选择 positive/negative/neutral 之一
4. noise: 是否为广告/无关内容 (true/false)
{noise_filter_section}
待分析内容：
标题: {title}
描述: {desc}

请严格按以下JSON格式返回，不要添加其他内容：
{{"summary": "...", "entities": {{"字段1": "值1", "字段2": "值2"}}, "sentiment": "positive/negative/neutral", "noise": false}}"""


@register_skill("cleaning", "ontology_cleaner")
class OntologyCleanerSkill(BaseCleaningSkill):
    """Domain-ontology-driven data cleaning with dynamic prompt generation."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "ontology_cleaner"

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

        entities_str = "、".join(required_entities) if required_entities else "无特定实体要求"

        return ONTOLOGY_PROMPT_TEMPLATE.format(
            domain_name=domain_name or "通用",
            required_entities=entities_str,
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

        prompt = await self.generate_prompt(domain_name, required_entities, noise_filters, title, desc)

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

            return {
                **item,
                "summary": analysis.get("summary", ""),
                "entities": analysis.get("entities", {}),
                "topics": list(analysis.get("entities", {}).keys()),
                "sentiment": analysis.get("sentiment", "neutral"),
                "noise": False,
            }

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[OntologyCleaner] LLM analysis failed for item: {e}")
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
