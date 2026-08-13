"""
LLM 客户端。

封装 Provider，提供重试、错误处理、日志等能力，是业务层调用 LLM
的唯一入口。
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from loguru import logger

from app.llm.provider import BaseProvider, get_provider
from app.llm.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ProviderConfig,
    StreamChunk,
)


class LLMClient:
    """LLM 客户端。

    Usage::

        config = ProviderConfig(provider="openai", base_url="https://api.deepseek.com/v1", model_name="deepseek-chat")
        client = LLMClient(config)
        response = await client.chat(messages=[ChatMessage(role="user", content="你好")])
        await client.close()

    也可从全局 settings 创建::

        client = LLMClient.from_settings()
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._provider: BaseProvider = get_provider(config)
        logger.bind(component="llm").info(
            "LLMClient initialized: provider={}, model={}, base_url={}",
            config.provider,
            config.model_name,
            config.base_url,
        )

    # -- 工厂方法 -----------------------------------------------------------

    @classmethod
    def from_settings(cls) -> LLMClient:
        """从全局 settings 创建客户端。"""
        from app.core.config import settings

        config = ProviderConfig(
            provider=settings.llm_provider,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model_name=settings.model_name,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )
        return cls(config)

    # -- 公共 API -----------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> ChatCompletionResponse:
        """发送非流式聊天请求。

        Parameters
        ----------
        messages:
            对话历史消息列表。
        model:
            模型名称，默认使用配置中的 model_name。
        temperature:
            采样温度，默认使用配置值。
        max_tokens:
            最大生成 token 数，默认使用配置值。
        tools:
            可用工具列表（OpenAI tools 协议），用于 function calling。

        Returns
        -------
        ChatCompletionResponse
            LLM 响应对象。
        """
        request = ChatCompletionRequest(
            model=model or self.config.model_name,
            messages=messages,
            temperature=temperature if temperature is not None else 0.7,
            max_tokens=max_tokens if max_tokens is not None else 2048,
            stream=False,
            tools=tools,
        )
        return await self._chat_with_retry(request)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """发送流式聊天请求。

        Parameters
        ----------
        messages:
            对话历史消息列表。
        model:
            模型名称，默认使用配置中的 model_name。
        temperature:
            采样温度，默认使用配置值。
        max_tokens:
            最大生成 token 数，默认使用配置值。

        Yields
        ------
        StreamChunk
            逐块产出的流式响应。
        """
        request = ChatCompletionRequest(
            model=model or self.config.model_name,
            messages=messages,
            temperature=temperature if temperature is not None else 0.7,
            max_tokens=max_tokens if max_tokens is not None else 2048,
            stream=True,
        )
        async for chunk in self._stream_chat_with_retry(request):
            yield chunk

    async def test_connection(self) -> dict:
        """测试 LLM 连通性。

        Returns
        -------
        dict
            包含 success（bool）、message（str）、latency_ms（int）。
        """
        import time

        start = time.perf_counter()
        try:
            messages = [
                ChatMessage(
                    role="user",
                    content="Reply with 'OK' only.",
                )
            ]
            response = await self.chat(messages, max_tokens=10)
            latency_ms = int((time.perf_counter() - start) * 1000)
            content = response.choices[0].message.content if response.choices else ""
            return {
                "success": True,
                "message": f"Connected. Response: {content}",
                "latency_ms": latency_ms,
                "model": response.model,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.bind(component="llm").error(
                "LLM connection test failed: {}", exc
            )
            return {
                "success": False,
                "message": str(exc),
                "latency_ms": latency_ms,
            }

    async def close(self) -> None:
        """关闭底层资源。"""
        await self._provider.close()
        logger.bind(component="llm").info("LLMClient closed")

    # -- 内部方法 -----------------------------------------------------------

    async def _chat_with_retry(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """带重试的非流式请求。"""
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return await self._provider.chat(request)
            except Exception as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    wait = 2**attempt  # 指数退避：1s, 2s, 4s, ...
                    logger.bind(component="llm").warning(
                        "LLM request failed (attempt {}/{}), retrying in {}s: {}",
                        attempt + 1,
                        self.config.max_retries + 1,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.bind(component="llm").error(
                        "LLM request failed after {} attempts: {}",
                        self.config.max_retries + 1,
                        exc,
                    )
        raise last_exc  # type: ignore[misc]

    async def _stream_chat_with_retry(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """带重试的流式请求。"""
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                async for chunk in self._provider.stream_chat(request):
                    yield chunk
                return  # 流式成功完成
            except Exception as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    wait = 2**attempt
                    logger.bind(component="llm").warning(
                        "LLM stream request failed (attempt {}/{}), retrying in {}s: {}",
                        attempt + 1,
                        self.config.max_retries + 1,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.bind(component="llm").error(
                        "LLM stream request failed after {} attempts: {}",
                        self.config.max_retries + 1,
                        exc,
                    )
        raise last_exc  # type: ignore[misc]


__all__ = ["LLMClient"]
