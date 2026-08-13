"""
Agent 模块 — 核心 Agent 内核。

提供 Planner、Executor、Memory、Manager 等核心组件，
实现从用户请求到 Agent 响应的端到端处理。
"""

from app.agent.memory import MemoryManager, MemoryEntry, ConversationMemory
from app.agent.planner import Planner, Plan, PlanStep
from app.agent.executor import Executor, StepResult, ExecutionResult
from app.agent.manager import AgentManager, AgentChatRequest, AgentChatResponse
from app.agent.prompts import get_system_prompt

__all__ = [
    # Memory
    "MemoryManager",
    "MemoryEntry",
    "ConversationMemory",
    # Planner
    "Planner",
    "Plan",
    "PlanStep",
    # Executor
    "Executor",
    "StepResult",
    "ExecutionResult",
    # Manager
    "AgentManager",
    "AgentChatRequest",
    "AgentChatResponse",
    # Prompts
    "get_system_prompt",
]
