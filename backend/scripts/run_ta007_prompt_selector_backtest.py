from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import AgentContext
from app.agents.keyword_expander_agent import KeywordExpanderAgent
from app.domain.services.keyword_prompt_selector import resolve_keyword_prompt_path


async def main() -> None:
    platforms = ["xiaohongshu", "douyin", "bilibili", "weibo", ""]
    selector_rows = []
    for platform in platforms:
        prompt_path, metadata = resolve_keyword_prompt_path(platform)
        selector_rows.append(
            {
                "platform": platform or "default",
                "selection_mode": metadata["selection_mode"],
                "prompt_key": metadata["prompt_key"],
                "prompt_path": str(prompt_path),
                "path_exists": prompt_path.exists(),
            }
        )

    agent = KeywordExpanderAgent()
    context = AgentContext(
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
    result = await agent.execute(context)
    if not result.success:
        raise SystemExit(result.error or "TA-007 backtest failed")

    print(
        json.dumps(
            {
                "task_id": "TA-007",
                "selector_rows": selector_rows,
                "plan_prompt_selector": result.data.get("prompt_selector", {}),
                "crawl_targets": result.data.get("crawl_targets", []),
                "task_candidate_count": len(result.data.get("task_candidates", [])),
                "expanded_keywords": result.data.get("expanded_keywords", []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
