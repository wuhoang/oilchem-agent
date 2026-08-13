"""
Agent 提示词模块。
"""

from app.agent.prompts.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    OILCHEM_DOMAIN_PROMPT,
    LAB_AUTOMATION_PROMPT,
    get_system_prompt,
    get_planning_prompt_template,
)

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "OILCHEM_DOMAIN_PROMPT",
    "LAB_AUTOMATION_PROMPT",
    "get_system_prompt",
    "get_planning_prompt_template",
]
