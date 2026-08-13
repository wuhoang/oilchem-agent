"""
输入护栏。

在用户输入送到 Agent 之前进行检查，过滤有害内容、
检测 Prompt 注入尝试、验证输入格式。
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger


class InputGuardrail:
    """输入护栏。

    检查用户输入是否安全，包括：
    - 有害关键词过滤
    - Prompt 注入检测
    - 输入长度限制
    - 敏感信息检测
    """

    # Prompt 注入特征
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
        r"disregard\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
        r"forget\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
        r"new\s+instructions?\s*:",
        r"system\s*prompt\s*:",
        r"\b(system|user|assistant)\s*:\s*",
        r"```system",
        r"jailbreak",
        r"dan\s+mode",
        r"do\s+anything\s+now",
    ]

    # 敏感信息模式（API Key、密码等）
    SENSITIVE_PATTERNS = [
        (r"api[_-]?key\s*[:=]\s*\S+", "[REDACTED]"),
        (r"password\s*[:=]\s*\S+", "[REDACTED]"),
        (r"secret\s*[:=]\s*\S+", "[REDACTED]"),
        (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]"),
        (r"AKIA[A-Z0-9]{16}", "[REDACTED_AWS_KEY]"),
    ]

    def __init__(self, max_length: int = 50000) -> None:
        self._max_length = max_length
        self._compiled_injection = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
        self._compiled_sensitive = [
            (re.compile(p, re.IGNORECASE), replacement)
            for p, replacement in self.SENSITIVE_PATTERNS
        ]

    def check(self, user_input: str) -> dict[str, Any]:
        """检查用户输入。

        Parameters
        ----------
        user_input:
            用户输入文本。

        Returns
        -------
        dict
            包含 passed (bool)、reason (str)、sanitized_input (str)。
        """
        if not user_input or not user_input.strip():
            return {
                "passed": False,
                "reason": "Input is empty",
                "sanitized_input": "",
            }

        # 长度检查
        if len(user_input) > self._max_length:
            return {
                "passed": False,
                "reason": f"Input exceeds max length ({len(user_input)} > {self._max_length})",
                "sanitized_input": user_input[: self._max_length],
            }

        # Prompt 注入检测
        for pattern in self._compiled_injection:
            if pattern.search(user_input):
                logger.bind(component="guardrails").warning(
                    "Prompt injection detected: pattern={}", pattern.pattern
                )
                return {
                    "passed": False,
                    "reason": "Potential prompt injection detected",
                    "sanitized_input": user_input,
                }

        # 敏感信息脱敏
        sanitized = user_input
        for pattern, replacement in self._compiled_sensitive:
            sanitized = pattern.sub(replacement, sanitized)

        return {
            "passed": True,
            "reason": "",
            "sanitized_input": sanitized,
        }


__all__ = ["InputGuardrail"]
