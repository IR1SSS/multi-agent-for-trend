from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config.settings import settings
from app.domain.services.keyword_expansion_service import normalize_platform_label

PLATFORM_PROMPT_FILES = {
    "xiaohongshu": "xiaohongshu.md",
    "douyin": "douyin.md",
    "bilibili": "bilibili.md",
}


def fallback_system_prompt() -> str:
    return (
        "你是一个专门为美妆护肤领域社交媒体爬虫服务的关键词扩充专家。"
        "根据用户提供的原始趋势关键词及其元数据，只补充少量更适合平台抓取的搜索词变体。"
        "所有搜索词必须明确指向护肤品、化妆品、个人护理相关内容。"
        "返回JSON格式：{\"expanded_keywords\": [\"词1\", \"词2\"]}"
    )


def _extract_system_prompt(markdown_path: Path) -> str:
    content = markdown_path.read_text(encoding="utf-8")
    marker = "### System Prompt"
    idx = content.find(marker)
    if idx == -1:
        raise ValueError(f"'### System Prompt' not found in {markdown_path}")

    after_marker = content[idx + len(marker):]
    code_start = after_marker.find("```")
    if code_start == -1:
        next_section = after_marker.find("\n## ")
        prompt_text = after_marker.strip() if next_section == -1 else after_marker[:next_section].strip()
    else:
        after_code_start = after_marker[code_start + 3:]
        newline_after_code = after_code_start.find("\n")
        if newline_after_code != -1:
            after_code_start = after_code_start[newline_after_code + 1:]
        code_end = after_code_start.find("```")
        prompt_text = after_code_start.strip() if code_end == -1 else after_code_start[:code_end].strip()

    if not prompt_text:
        raise ValueError(f"Empty system prompt extracted from {markdown_path}")
    return prompt_text


def resolve_keyword_prompt_path(platform: str | None) -> tuple[Path, dict[str, str]]:
    default_path = Path(settings.KEYWORD_SKILL_PATH)
    normalized_platform = normalize_platform_label(platform or "")
    prompt_dir = Path(settings.KEYWORD_PLATFORM_PROMPT_DIR)
    prompt_filename = PLATFORM_PROMPT_FILES.get(normalized_platform)

    if prompt_filename:
        candidate_path = prompt_dir / prompt_filename
        if candidate_path.exists():
            return candidate_path, {
                "platform": normalized_platform,
                "selection_mode": "platform_specific",
                "prompt_key": normalized_platform,
                "prompt_path": str(candidate_path),
            }
        return default_path, {
            "platform": normalized_platform,
            "selection_mode": "fallback_missing_platform_prompt",
            "prompt_key": "default",
            "prompt_path": str(default_path),
        }

    return default_path, {
        "platform": normalized_platform or "default",
        "selection_mode": "fallback_default",
        "prompt_key": "default",
        "prompt_path": str(default_path),
    }


@lru_cache(maxsize=8)
def load_platform_system_prompt(platform: str | None) -> tuple[str, dict[str, str]]:
    prompt_path, metadata = resolve_keyword_prompt_path(platform)
    if not prompt_path.exists():
        fallback_meta = dict(metadata)
        fallback_meta["selection_mode"] = "fallback_builtin"
        return fallback_system_prompt(), fallback_meta

    try:
        return _extract_system_prompt(prompt_path), metadata
    except (OSError, ValueError):
        fallback_meta = dict(metadata)
        fallback_meta["selection_mode"] = "fallback_builtin"
        fallback_meta["prompt_path"] = str(prompt_path)
        return fallback_system_prompt(), fallback_meta
