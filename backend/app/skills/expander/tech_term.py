"""Tech-term expansion skill — "技术术语-衍生应用" two-level expansion.

Strategy for emerging industries (new energy vehicles, AI tools, etc.)
where the vocabulary is more technical and less consumer-oriented.
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.config.settings import settings
from app.domain_meta.registry import register_skill
from app.skills.expander.base import BaseExpanderSkill

logger = logging.getLogger(__name__)

TECH_TERM_SYSTEM_TEMPLATE = """你是一个专门为{domain_name}领域服务的关键词扩展专家。

你的任务是通过"技术术语 → 衍生应用"两级结构扩展搜索关键词。

严格约束：
1. 第一层级：提取该领域的技术术语和核心概念
2. 第二层级：基于技术术语扩展出衍生应用场景和用户关注点
3. 以下关键词为负向词，绝对不能出现在扩展结果中：{negative_keywords}
4. 扩展深度不超过 {max_depth} 层

返回JSON格式：
{{"expanded_keywords": [{{"keyword": "扩展词", "depth": 1, "parent": "原始关键词"}}]}}"""

TECH_TERM_USER_TEMPLATE = """原始关键词: {keyword}
领域: {domain_name}
已有变体: {existing_variants}

请从技术术语和衍生应用两个层级生成扩展搜索词。"""


@register_skill("expander", "tech_term")
class TechTermExpanderSkill(BaseExpanderSkill):
    """Two-level tech-term keyword expansion for emerging industries."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def strategy_name(self) -> str:
        return "tech_term"

    async def expand(
        self,
        keyword: str,
        domain_name: str,
        negative_keywords: list[str],
        max_depth: int,
        extra: dict | None = None,
    ) -> list[dict]:
        extra = extra or {}
        existing_variants = extra.get("query_variants", "")

        system_prompt = TECH_TERM_SYSTEM_TEMPLATE.format(
            domain_name=domain_name or "科技",
            negative_keywords="、".join(negative_keywords) if negative_keywords else "无",
            max_depth=max_depth,
        )

        user_prompt = TECH_TERM_USER_TEMPLATE.format(
            keyword=keyword,
            domain_name=domain_name or "科技",
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
                max_tokens=500,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = self._strip_code_block(content)
            result = json.loads(content)
            expanded = result.get("expanded_keywords", [])

            if not isinstance(expanded, list):
                return []

            filtered = []
            for item in expanded:
                kw = item.get("keyword", "") if isinstance(item, dict) else str(item)
                if any(neg in kw for neg in negative_keywords):
                    continue
                filtered.append({
                    "keyword": kw,
                    "depth": item.get("depth", 1) if isinstance(item, dict) else 1,
                    "parent": item.get("parent", keyword) if isinstance(item, dict) else keyword,
                })

            return filtered

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[TechTermExpander] LLM call failed: {e}")
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
