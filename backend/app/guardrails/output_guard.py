"""
输出护栏。

在 Agent 输出返回给用户之前进行检查，
过滤有害内容、检查输出格式、防止敏感信息泄露。
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger


class OutputGuardrail:
    """输出护栏。

    检查 Agent 输出是否安全合规。
    """

    # 有害内容特征
    HARMFUL_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
        r"disregard\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
    ]

    # 敏感信息泄露模式
    LEAK_PATTERNS = [
        (r"api[_-]?key\s*[:=]\s*\S+", "[REDACTED]"),
        (r"password\s*[:=]\s*\S+", "[REDACTED]"),
        (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]"),
        (r"AKIA[A-Z0-9]{16}", "[REDACTED_AWS_KEY]"),
    ]

    def __init__(self) -> None:
        self._compiled_harmful = [
            re.compile(p, re.IGNORECASE) for p in self.HARMFUL_PATTERNS
        ]
        self._compiled_leak = [
            (re.compile(p, re.IGNORECASE), replacement)
            for p, replacement in self.LEAK_PATTERNS
        ]

    def check(self, output: str) -> dict[str, Any]:
        """检查 Agent 输出。

        Parameters
        ----------
        output:
            Agent 输出文本。

        Returns
        -------
        dict
            包含 passed (bool)、reason (str)、sanitized_output (str)。
        """
        if not output:
            return {
                "passed": True,
                "reason": "",
                "sanitized_output": "",
            }

        # 检查有害内容
        for pattern in self._compiled_harmful:
            if pattern.search(output):
                logger.bind(component="guardrails").warning(
                    "Harmful content detected in output: pattern={}", pattern.pattern
                )
                return {
                    "passed": False,
                    "reason": "Harmful content detected in output",
                    "sanitized_output": output,
                }

        # 脱敏敏感信息
        sanitized = output
        for pattern, replacement in self._compiled_leak:
            sanitized = pattern.sub(replacement, sanitized)

        return {
            "passed": True,
            "reason": "",
            "sanitized_output": sanitized,
        }


__all__ = ["OutputGuardrail"]
