"""
Agent 内存模块。

提供会话级短期记忆（对话历史）和长期记忆（知识库摘要），
支持上下文窗口自动压缩，避免超出 LLM token 限制。
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.llm.schemas import ChatMessage, MessageRole


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class MemoryEntry(BaseModel):
    """单条记忆条目。"""

    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    timestamp: float = Field(default_factory=time.time, description="时间戳")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ConversationMemory(BaseModel):
    """会话记忆（短期）。"""

    session_id: str = Field(..., description="会话 ID")
    messages: list[MemoryEntry] = Field(default_factory=list, description="消息历史")
    summary: str = Field(default="", description="历史摘要（当消息过多时生成）")
    max_messages: int = Field(default=20, description="最大保留消息数（超出自动压缩）")


# ---------------------------------------------------------------------------
# 会话内存管理器
# ---------------------------------------------------------------------------

class MemoryManager:
    """会话内存管理器。

    管理所有会话的短期记忆，提供增删查改和自动摘要压缩能力。

    Usage::

        mm = MemoryManager()
        mm.add_message("session-1", role="user", content="你好")
        context = mm.get_context("session-1")
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationMemory] = {}
        self._global_knowledge: list[dict[str, Any]] = []
        logger.bind(component="memory").info("MemoryManager initialized")

    # -- 会话管理 -----------------------------------------------------------

    def create_session(self, session_id: str) -> ConversationMemory:
        """创建新会话。"""
        if session_id in self._sessions:
            logger.bind(component="memory").warning(
                "Session already exists: {}", session_id
            )
            return self._sessions[session_id]
        memory = ConversationMemory(session_id=session_id)
        self._sessions[session_id] = memory
        logger.bind(component="memory").debug("Session created: {}", session_id)
        return memory

    def get_session(self, session_id: str) -> ConversationMemory | None:
        """获取会话记忆。"""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        """删除会话。"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.bind(component="memory").debug("Session deleted: {}", session_id)

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID。"""
        return list(self._sessions.keys())

    # -- 消息操作 -----------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMemory:
        """添加消息到会话。"""
        session = self._sessions.get(session_id)
        if session is None:
            session = self.create_session(session_id)

        entry = MemoryEntry(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        session.messages.append(entry)

        # 自动压缩：超过 max_messages 时进行摘要
        if len(session.messages) > session.max_messages:
            self._compress_session(session)

        return session

    def get_context(
        self, session_id: str, include_system: bool = True
    ) -> list[ChatMessage]:
        """获取会话上下文，转换为 LLM 所需的消息格式。

        Parameters
        ----------
        session_id:
            会话 ID。
        include_system:
            是否在开头包含系统消息摘要。

        Returns
        -------
        list[ChatMessage]
            按时间顺序排列的消息列表。
        """
        session = self._sessions.get(session_id)
        if session is None:
            return []

        messages: list[ChatMessage] = []

        # 添加摘要作为系统消息
        if include_system and session.summary:
            messages.append(
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=f"Previous conversation summary:\n{session.summary}",
                )
            )

        # 添加最近的消息
        for entry in session.messages:
            messages.append(
                ChatMessage(role=entry.role, content=entry.content)
            )

        return messages

    def get_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[MemoryEntry]:
        """获取会话的原始消息条目。"""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        if limit is not None:
            return session.messages[-limit:]
        return session.messages

    # -- 长期知识 -----------------------------------------------------------

    def add_knowledge(self, content: str, source: str = "unknown") -> None:
        """添加长期知识条目。"""
        self._global_knowledge.append(
            {
                "content": content,
                "source": source,
                "timestamp": time.time(),
            }
        )
        logger.bind(component="memory").debug(
            "Knowledge added: {} (source={})", content[:50], source
        )

    def get_knowledge(self, limit: int = 20) -> list[dict[str, Any]]:
        """获取长期知识条目。"""
        return self._global_knowledge[-limit:]

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        """简单关键词搜索（后续可替换为向量检索）。"""
        query_lower = query.lower()
        results = []
        for item in self._global_knowledge:
            if query_lower in item["content"].lower():
                results.append(item)
        return results

    # -- 内部方法 -----------------------------------------------------------

    def _compress_session(self, session: ConversationMemory) -> None:
        """压缩会话：保留最近消息，旧消息生成摘要。"""
        keep_count = session.max_messages // 2
        old_messages = session.messages[:-keep_count]
        recent_messages = session.messages[-keep_count:]

        # 简单摘要：拼接旧消息内容（后续可接入 LLM 生成摘要）
        summary_parts = []
        for msg in old_messages:
            summary_parts.append(f"[{msg.role.value}]: {msg.content[:100]}")

        new_summary = f"{session.summary}\n" + "\n".join(summary_parts)
        session.summary = new_summary.strip()
        session.messages = recent_messages

        logger.bind(component="memory").debug(
            "Session {} compressed: {} messages → {} messages + summary",
            session.session_id,
            len(old_messages),
            len(recent_messages),
        )


__all__ = [
    "MemoryEntry",
    "ConversationMemory",
    "MemoryManager",
]
