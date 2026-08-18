"""
Agent 模块 — 核心 Agent 内核。

提供 Memory、Manager、Prompts 等核心组件，
实现从用户请求到 Agent 响应的端到端处理（原生 function calling 链路）。
"""

from app.agent.memory import MemoryManager, MemoryEntry, ConversationMemory
from app.agent.manager import AgentManager, AgentChatRequest, AgentChatResponse
from app.agent.prompts import get_system_prompt

__all__ = [
    # Memory
    "MemoryManager",
    "MemoryEntry",
    "ConversationMemory",
    # Manager
    "AgentManager",
    "AgentChatRequest",
    "AgentChatResponse",
    # Prompts
    "get_system_prompt",
]
