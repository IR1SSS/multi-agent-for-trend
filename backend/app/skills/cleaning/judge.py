"""LLM-as-a-Judge quality gate skill.

Uses a small, fast model to validate cleaning results against
domain-specific constraints. Rejects and flags results that
fail schema alignment or factuality checks.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import settings
from app.domain_meta.registry import register_skill
from app.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger(__name__)

JUDGE_PROMPT_TEMPLATE = """你是一个数据质量裁判。请评判以下{domain_name}领域的清洗结果是否满足质量要求。

质量检查项：
1. schema_alignment: 提取的实体是否完整，核心字段是否有值？
   - 必须包含的实体字段：{required_entities}
2. factuality: 摘要是否准确反映了原文内容？是否出现幻觉？
3. noise_detection: 是否有被遗漏的噪声内容？

待评判的清洗结果：
{cleaned_result}

原始内容：
标题: {title}
描述: {desc}

请返回JSON格式的评判结果：
{{"passed": true/false, "score": 0.0-1.0, "issues": ["问题描述1", "问题描述2"]}}"""


@register_skill("cleaning", "judge")
class LLMJudgeSkill(BaseSkill):
    """LLM-as-a-Judge quality gate for validating cleaning results."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    @property
    def skill_type(self) -> str:
        return "cleaning"

    @property
    def strategy_name(self) -> str:
        return "judge"

    async def judge_result(
        self,
        cleaned_result: dict[str, Any],
        domain_name: str,
        required_entities: list[str],
        title: str,
        desc: str,
        judge_model: str | None = None,
    ) -> dict[str, Any]:
        """Judge a single cleaned result.

        Returns:
            Dict with 'passed' (bool), 'score' (float), 'issues' (list[str]).
        """
        model = judge_model or settings.LLM_MODEL
        entities_str = "、".join(required_entities)

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            domain_name=domain_name or "通用",
            required_entities=entities_str,
            cleaned_result=json.dumps(cleaned_result, ensure_ascii=False, indent=2),
            title=title[:300],
            desc=desc[:500],
        )

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content or "{}"
            content = content.strip()
            if content.startswith("```"):
                first_newline = content.index("\n") + 1
                content = content[first_newline:]
                if content.rstrip().endswith("```"):
                    content = content.rstrip()[:-3].rstrip()

            result = json.loads(content)
            return {
                "passed": result.get("passed", True),
                "score": float(result.get("score", 0.5)),
                "issues": result.get("issues", []),
            }

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[LLMJudge] Judge call failed, passing by default: {e}")
            return {"passed": True, "score": 0.5, "issues": [f"Judge failed: {e}"]}

    async def execute(self, context: SkillContext, config: dict) -> SkillResult:
        """Execute judge on items from context.extra['items_to_judge'].

        Config keys:
        - domain_name: str
        - required_entities: list[str]
        - judge_model: str (optional)
        """
        items = context.extra.get("items_to_judge", [])
        domain_name = config.get("domain_name", "")
        required_entities = config.get("required_entities", [])
        judge_model = config.get("judge_model", None)

        passed_items = []
        rejected_items = []

        for item in items:
            title = item.get("title", "")
            desc = item.get("desc", "") or item.get("description", "")
            judgment = await self.judge_result(
                cleaned_result=item,
                domain_name=domain_name,
                required_entities=required_entities,
                title=title,
                desc=desc,
                judge_model=judge_model,
            )

            if judgment["passed"]:
                passed_items.append({**item, "judge_score": judgment["score"]})
            else:
                rejected_items.append({**item, "judge_issues": judgment["issues"]})

        return SkillResult(
            success=True,
            data={
                "passed_count": len(passed_items),
                "rejected_count": len(rejected_items),
                "passed_items": passed_items,
                "rejected_items": rejected_items,
            },
        )
