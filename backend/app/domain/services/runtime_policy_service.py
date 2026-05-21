from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_RUNTIME_PROFILE = "safe_live"

RUNTIME_POLICY_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "safe_live": {
        "default": {
            "per_platform_limit": 1,
            "login_type": "cookie",
            "headless": False,
            "enable_comments": True,
            "enable_sub_comments": False,
            "max_notes_count": 50,
            "max_comments_per_note": 200,
            "max_concurrency": 1,
            "allow_local_state_fallback": False,
            "max_raw_items": 50,
            "max_tasks_per_keyword": 1,
            "dedup_window_hours": 168,
            "retry_cooldown_hours": 24,
            "max_transient_attempts": 1,
            "retry_backoff_seconds": 0,
            "task_delay_seconds": 10,
            "operator_note": "Use moderate per-keyword sampling: about 50 posts and up to 200 first-level comments per post.",
        },
        "xhs": {
            "task_delay_seconds": 20,
            "retry_cooldown_hours": 72,
            "operator_note": "Treat xhs as sparse manual verification only. Avoid repeated smoke on the same account.",
        },
        "dy": {
            "max_transient_attempts": 2,
            "retry_backoff_seconds": 20,
            "task_delay_seconds": 10,
            "retry_cooldown_hours": 24,
            "operator_note": "Prefer dy for repeated runtime verification before widening xhs coverage.",
        },
        "bili": {
            "max_transient_attempts": 2,
            "retry_backoff_seconds": 20,
            "task_delay_seconds": 8,
            "retry_cooldown_hours": 12,
            "operator_note": "bili is the lowest-risk live verification path among the current supported platforms.",
        },
    },
    "debug_fast": {
        "default": {
            "per_platform_limit": 1,
            "login_type": "cookie",
            "headless": False,
            "enable_comments": True,
            "enable_sub_comments": False,
            "max_notes_count": 50,
            "max_comments_per_note": 200,
            "max_concurrency": 1,
            "allow_local_state_fallback": True,
            "max_raw_items": 50,
            "max_tasks_per_keyword": 1,
            "dedup_window_hours": 24,
            "retry_cooldown_hours": 6,
            "max_transient_attempts": 2,
            "retry_backoff_seconds": 3,
            "task_delay_seconds": 0,
            "operator_note": "Use moderate per-keyword sampling for local debugging or replay.",
        },
    },
}


def resolve_runtime_policy(
    platform: str,
    *,
    profile_name: str = DEFAULT_RUNTIME_PROFILE,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = RUNTIME_POLICY_PROFILES.get(profile_name)
    if not profile:
        raise ValueError(f"Unsupported runtime profile: {profile_name}")

    effective = deepcopy(profile["default"])
    effective.update(profile.get(platform, {}))

    for key, value in (overrides or {}).items():
        if value is not None:
            effective[key] = value

    effective["platform"] = platform
    effective["profile_name"] = profile_name
    return effective
