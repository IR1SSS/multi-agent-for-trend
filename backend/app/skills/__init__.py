"""Skills package — pluggable skill implementations.

Each sub-package corresponds to a skill type and contains:
- base.py: Abstract base class for that skill type
- One or more strategy implementations

Skills auto-register with the global SkillRegistry via @register_skill.
"""
from app.skills.base import BaseSkill, SkillContext, SkillResult

# Import all skill sub-packages to trigger registration
from app.skills import expander  # noqa: F401
from app.skills import cleaning  # noqa: F401
from app.skills import insight   # noqa: F401

__all__ = ["BaseSkill", "SkillContext", "SkillResult"]
