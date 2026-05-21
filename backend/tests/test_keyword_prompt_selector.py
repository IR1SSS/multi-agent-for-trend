from __future__ import annotations

import unittest

from app.agents.base import AgentContext
from app.agents.keyword_expander_agent import KeywordExpanderAgent
from app.domain.services.keyword_prompt_selector import resolve_keyword_prompt_path


class KeywordPromptSelectorTests(unittest.IsolatedAsyncioTestCase):
    def test_platform_specific_prompt_resolution(self) -> None:
        cases = {
            "xiaohongshu": "xiaohongshu",
            "douyin": "douyin",
            "bilibili": "bilibili",
        }
        for platform, prompt_key in cases.items():
            prompt_path, meta = resolve_keyword_prompt_path(platform)
            self.assertTrue(prompt_path.exists())
            self.assertEqual(meta["selection_mode"], "platform_specific")
            self.assertEqual(meta["prompt_key"], prompt_key)

    def test_unknown_platform_falls_back_to_default(self) -> None:
        prompt_path, meta = resolve_keyword_prompt_path("weibo")
        self.assertTrue(prompt_path.exists())
        self.assertEqual(meta["selection_mode"], "fallback_default")
        self.assertEqual(meta["prompt_key"], "default")

    async def test_execute_exposes_prompt_selector_without_llm(self) -> None:
        agent = KeywordExpanderAgent()
        result = await agent.execute(
            AgentContext(
                keyword="快速美白",
                extra={
                    "keyword_id": "KW_0040",
                    "normalized_keyword": "快速美白",
                    "topic_cluster": "claim_risk_watch",
                    "trend_type": "claim",
                    "query_variants": "7天美白|28天焕白",
                    "suggested_platforms": "xiaohongshu|douyin|bilibili",
                    "crawl_goal": "risk_monitoring",
                    "risk_flag": "high",
                    "priority": "high",
                    "confidence": "medium",
                    "enable_llm": False,
                },
            )
        )

        self.assertTrue(result.success)
        prompt_selector = result.data.get("prompt_selector", {})
        self.assertEqual(set(prompt_selector.keys()), {"xiaohongshu", "douyin", "bilibili"})
        self.assertEqual(prompt_selector["xiaohongshu"]["prompt_key"], "xiaohongshu")
        self.assertEqual(prompt_selector["douyin"]["prompt_key"], "douyin")
        self.assertEqual(prompt_selector["bilibili"]["prompt_key"], "bilibili")
        self.assertGreater(len(result.data.get("task_candidates", [])), 0)

