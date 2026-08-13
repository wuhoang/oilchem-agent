"""
LLM 提供商抽象层。

提供统一的 LLM 调用接口，屏蔽不同提供商（OpenAI、Ollama、通义等）
的 API 差异。新增提供商只需继承 BaseProvider 并实现 _do_chat /
_do_stream_chat 方法。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx
from loguru import logger

from app.llm.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ProviderConfig,
    StreamChunk,
)


# ---------------------------------------------------------------------------
# 提供商映射表
# ---------------------------------------------------------------------------

# 全局注册表：provider 类型名 → Provider 类
_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {}


def register_provider(provider_type: str):
    """提供商注册装饰器。

    Usage::

        @register_provider("ollama")
        class OllamaProvider(BaseProvider):
            ...
    """

    def decorator(cls: type[BaseProvider]) -> type[BaseProvider]:
        if provider_type in _PROVIDER_REGISTRY:
            raise ValueError(f"Provider '{provider_type}' already registered")
        _PROVIDER_REGISTRY[provider_type] = cls
        logger.bind(component="llm").debug("Registered provider: {}", provider_type)
        return cls

    return decorator


def get_provider(config: ProviderConfig) -> BaseProvider:
    """根据配置创建对应的提供商实例。"""
    provider_cls = _PROVIDER_REGISTRY.get(config.provider)
    if provider_cls is None:
        supported = list(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unsupported provider '{config.provider}'. Supported: {supported}"
        )
    return provider_cls(config)


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """LLM 提供商抽象基类。

    子类必须实现 :meth:`_do_chat` 和 :meth:`_do_stream_chat`。
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        """构建 HTTP 请求头。"""
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    # -- 公共方法 -----------------------------------------------------------

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """发送非流式聊天补全请求。"""
        payload = self._build_payload(request, stream=False)
        logger.bind(component="llm").debug(
            "Sending chat request to {} (model={}, messages={})",
            self.config.provider,
            request.model,
            len(request.messages),
        )
        data = await self._do_chat(payload)
        return self._parse_response(data)

    async def stream_chat(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """发送流式聊天补全请求，逐块产出 StreamChunk。"""
        payload = self._build_payload(request, stream=True)
        logger.bind(component="llm").debug(
            "Sending stream chat request to {} (model={})",
            self.config.provider,
            request.model,
        )
        async for chunk in self._do_stream_chat(payload):
            parsed = self._parse_stream_chunk(chunk)
            if parsed is not None:
                yield parsed

    async def close(self) -> None:
        """关闭底层 HTTP 客户端。"""
        await self._client.aclose()

    # -- 子类需实现 ---------------------------------------------------------

    @abstractmethod
    async def _do_chat(self, payload: dict) -> dict:
        """执行非流式请求，返回 JSON 字典。"""

    @abstractmethod
    async def _do_stream_chat(self, payload: dict) -> AsyncIterator[dict]:
        """执行流式请求，逐块产出原始 JSON 字典。"""

    # -- 解析方法（可被子类覆盖） -------------------------------------------

    def _build_payload(
        self, request: ChatCompletionRequest, stream: bool
    ) -> dict:
        """将 ChatCompletionRequest 转换为提供商特定的请求体。"""
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
        ]
        payload: dict = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": stream,
        }
        if request.tools:
            payload["tools"] = request.tools
        return payload

    def _parse_response(self, data: dict) -> ChatCompletionResponse:
        """将提供商响应解析为 ChatCompletionResponse。"""
        choices = []
        for c in data.get("choices", []):
            msg = c.get("message", {})
            choices.append(
                {
                    "index": c.get("index", 0),
                    "message": {
                        "role": msg.get("role", "assistant"),
                        "content": msg.get("content", ""),
                    },
                    "finish_reason": c.get("finish_reason"),
                }
            )
        usage_data = data.get("usage", {})
        return ChatCompletionResponse(
            id=data.get("id", ""),
            choices=choices,
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            },
            model=data.get("model", ""),
        )

    def _parse_stream_chunk(self, data: dict) -> StreamChunk | None:
        """解析单个流式块，返回 StreamChunk；无内容时返回 None。"""
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        delta_data = choice.get("delta", {})
        content = delta_data.get("content")
        role = delta_data.get("role")
        finish_reason = choice.get("finish_reason")

        if not content and not role and not finish_reason:
            return None

        return StreamChunk(
            id=data.get("id", ""),
            delta={
                "role": role,
                "content": content,
            },
            finish_reason=finish_reason,
        )


# ---------------------------------------------------------------------------
# OpenAI 兼容提供商
# ---------------------------------------------------------------------------

@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """OpenAI API 兼容提供商（含阿里云、Azure 等兼容端点）。"""

    async def _do_chat(self, payload: dict) -> dict:
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def _do_stream_chat(self, payload: dict) -> AsyncIterator[dict]:
        async with self._client.stream(
            "POST", "/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        logger.bind(component="llm").warning(
                            "Failed to parse SSE line: {}", raw[:120]
                        )


# ---------------------------------------------------------------------------
# Ollama 本地提供商
# ---------------------------------------------------------------------------

@register_provider("ollama")
class OllamaProvider(BaseProvider):
    """Ollama 本地部署提供商。"""

    def _build_headers(self) -> dict[str, str]:
        # Ollama 默认不需要认证
        return {"Content-Type": "application/json"}

    def _build_payload(
        self, request: ChatCompletionRequest, stream: bool
    ) -> dict:
        # Ollama 使用 messages 格式，与 OpenAI 兼容
        payload = super()._build_payload(request, stream)
        return payload

    async def _do_chat(self, payload: dict) -> dict:
        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        return response.json()

    async def _do_stream_chat(self, payload: dict) -> AsyncIterator[dict]:
        # Ollama 流式为 NDJSON（每行一个 JSON 对象）
        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        logger.bind(component="llm").warning(
                            "Failed to parse Ollama NDJSON line: {}", line[:120]
                        )

    def _parse_response(self, data: dict) -> ChatCompletionResponse:
        """Ollama 响应格式略有不同，需要适配。"""
        message = data.get("message", {})
        return ChatCompletionResponse(
            id=data.get("id", ""),
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": message.get("role", "assistant"),
                        "content": message.get("content", ""),
                    },
                    "finish_reason": data.get("done_reason"),
                }
            ],
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0)
                + data.get("eval_count", 0),
            },
            model=data.get("model", ""),
        )

    def _parse_stream_chunk(self, data: dict) -> StreamChunk | None:
        """Ollama 流式块解析。"""
        message = data.get("message", {})
        content = message.get("content")
        role = message.get("role")
        done = data.get("done", False)
        finish_reason = data.get("done_reason") if done else None

        if not content and not role and not finish_reason:
            return None

        return StreamChunk(
            id=data.get("id", ""),
            delta={
                "role": role,
                "content": content,
            },
            finish_reason=finish_reason,
        )


__all__ = [
    "BaseProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "register_provider",
    "get_provider",
]
