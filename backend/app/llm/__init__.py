"""
LLM 模块 —— 统一的大模型调用接口。

快速上手::

    from app.llm import LLMClient, ChatMessage

    client = LLMClient.from_settings()
    response = await client.chat([ChatMessage(role="user", content="你好")])
"""

from app.llm.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatCompletionChoice,
    MessageRole,
    ProviderConfig,
    StreamChunk,
    StreamDelta,
    Usage,
)
from app.llm.provider import (
    BaseProvider,
    OpenAIProvider,
    OllamaProvider,
    get_provider,
    register_provider,
)
from app.llm.client import LLMClient

__all__ = [
    # schemas
    "MessageRole",
    "ChatMessage",
    "ChatCompletionRequest",
    "ChatCompletionChoice",
    "ChatCompletionResponse",
    "Usage",
    "StreamDelta",
    "StreamChunk",
    "ProviderConfig",
    # provider
    "BaseProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "register_provider",
    "get_provider",
    # client
    "LLMClient",
]
