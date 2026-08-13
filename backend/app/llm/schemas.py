"""
LLM 交互数据模型。

定义 LLM 请求/响应的 Pydantic 模型，统一各提供商（OpenAI、
Ollama、通义等）的数据结构，屏蔽底层 API 差异。
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class MessageRole(str, Enum):
    """聊天消息角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """单条聊天消息。"""

    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息文本内容")
    # function calling 支持
    tool_call_id: str | None = Field(default=None, description="工具调用 ID（role=tool 消息使用）")
    tool_calls: list[dict] | None = Field(default=None, description="工具调用请求（assistant 消息使用）")

    model_config = {"json_schema_extra": {"example": {"role": "user", "content": "你好"}}}


class ChatCompletionRequest(BaseModel):
    """聊天补全请求。"""

    model: str = Field(..., description="模型名称")
    messages: list[ChatMessage] = Field(..., description="历史消息列表")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="采样温度")
    max_tokens: int = Field(default=2048, gt=0, description="最大生成 token 数")
    stream: bool = Field(default=False, description="是否流式响应")
    # 预留：工具调用
    tools: list[dict] | None = Field(default=None, description="可用工具列表")


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------

class Usage(BaseModel):
    """Token 用量统计。"""

    prompt_tokens: int = Field(default=0, description="输入 token 数")
    completion_tokens: int = Field(default=0, description="输出 token 数")
    total_tokens: int = Field(default=0, description="总 token 数")


class ChatCompletionChoice(BaseModel):
    """补全结果选项。"""

    index: int = Field(default=0, description="选项索引")
    message: ChatMessage = Field(..., description="生成的消息")
    finish_reason: str | None = Field(default=None, description="结束原因")


class ChatCompletionResponse(BaseModel):
    """聊天补全响应。"""

    id: str = Field(..., description="响应唯一标识")
    choices: list[ChatCompletionChoice] = Field(..., description="补全选项列表")
    usage: Usage = Field(default_factory=Usage, description="Token 用量")
    model: str = Field(default="", description="实际使用的模型名称")


# ---------------------------------------------------------------------------
# 流式响应块
# ---------------------------------------------------------------------------

class StreamDelta(BaseModel):
    """流式响应增量。"""

    role: MessageRole | None = Field(default=None, description="消息角色（仅首块）")
    content: str | None = Field(default=None, description="增量文本内容")


class StreamChunk(BaseModel):
    """流式响应块。"""

    id: str = Field(..., description="响应唯一标识")
    delta: StreamDelta = Field(..., description="增量内容")
    finish_reason: str | None = Field(default=None, description="结束原因")


# ---------------------------------------------------------------------------
# 提供商配置
# ---------------------------------------------------------------------------

class ProviderConfig(BaseModel):
    """LLM 提供商配置。"""

    provider: Literal["openai", "ollama", "qianwen"] = Field(
        default="openai", description="提供商类型"
    )
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥（本地部署可留空）")
    model_name: str = Field(..., description="默认模型名称")
    timeout: float = Field(default=30.0, gt=0, description="请求超时（秒）")
    max_retries: int = Field(default=2, ge=0, description="最大重试次数")


__all__ = [
    "MessageRole",
    "ChatMessage",
    "ChatCompletionRequest",
    "Usage",
    "ChatCompletionChoice",
    "ChatCompletionResponse",
    "StreamDelta",
    "StreamChunk",
    "ProviderConfig",
]
