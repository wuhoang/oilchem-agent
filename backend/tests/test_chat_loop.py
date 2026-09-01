"""核心聊天循环测试（chat_with_tools / chat_stream_with_tools）。

通过 mock LLM 和工具，验证 Agent 循环的关键路径：
无工具直接回答、单工具、多工具、重复检测、超时、失败降级。
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.manager import AgentChatRequest, AgentManager
from app.llm.schemas import (
    ChatCompletionResponse,
    ChatMessage,
    MessageRole,
)
from app.tools.base import ToolResult


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_response(
    content: str = "",
    tool_calls: list[dict] | None = None,
) -> ChatCompletionResponse:
    """构造一个 LLM 响应对象。"""
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return ChatCompletionResponse(
        id="test-resp",
        choices=[{"index": 0, "message": msg, "finish_reason": "stop"}],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        model="test-model",
    )


def _make_tool_call(tool_name: str, args: dict, call_id: str = "call_1") -> dict:
    """构造一个 tool_call 结构。"""
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def _make_manager() -> AgentManager:
    """构造一个 AgentManager，LLM 和 ToolManager 都是 mock。"""
    with patch("app.agent.manager.LLMClient"), \
         patch("app.agent.manager.ToolManager"), \
         patch("app.agent.manager.MemoryManager"):
        mgr = AgentManager()
    return mgr


# ---------------------------------------------------------------------------
# chat_with_tools 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_tool_direct_answer():
    """用户问知识类问题 → LLM 直接回答，不调工具。"""
    mgr = _make_manager()
    mgr._llm.chat = AsyncMock(return_value=_make_response(content="漏失量正常范围 ≤15mL"))

    resp = await mgr.chat_with_tools(AgentChatRequest(message="HTHP漏失量正常范围"))
    assert resp.success
    assert "15mL" in resp.response
    assert resp.plan_steps == 0
    assert resp.plan_used is False


@pytest.mark.asyncio
async def test_single_tool_call():
    """LLM 调一次工具 → 拿到结果 → 给出回答。"""
    mgr = _make_manager()
    tool_call = _make_tool_call("read_hardware", {"device_id": "HTHP-01"})

    mgr._llm.chat = AsyncMock(side_effect=[
        _make_response(tool_calls=[tool_call]),
        _make_response(content="HTHP-01 当前温度 25.3°C"),
    ])
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=True, data={"temperature": 25.3, "unit": "°C"})
    )

    resp = await mgr.chat_with_tools(AgentChatRequest(message="HTHP-01温度多少"))
    assert resp.success
    assert "25.3" in resp.response
    assert resp.plan_steps == 1
    assert resp.plan_used is True


@pytest.mark.asyncio
async def test_two_tool_calls():
    """LLM 调两次不同工具 → 都成功 → 给出回答。"""
    mgr = _make_manager()
    tc1 = _make_tool_call("read_hardware", {"device_id": "HTHP-01"}, "call_1")
    tc2 = _make_tool_call("query_hardware_history", {"device_id": "HTHP-01"}, "call_2")

    mgr._llm.chat = AsyncMock(side_effect=[
        _make_response(tool_calls=[tc1]),
        _make_response(tool_calls=[tc2]),
        _make_response(content="温度稳定在25°C左右"),
    ])
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=True, data={"values": [25.0, 25.1, 25.3]})
    )

    resp = await mgr.chat_with_tools(AgentChatRequest(message="HTHP-01温度趋势"))
    assert resp.success
    assert resp.plan_steps == 2


@pytest.mark.asyncio
async def test_duplicate_tool_call_stops():
    """重复调用同一工具+相同参数 → 强制停止。"""
    mgr = _make_manager()
    tc = _make_tool_call("read_hardware", {"device_id": "HTHP-01"})

    mgr._llm.chat = AsyncMock(side_effect=[
        _make_response(tool_calls=[tc]),
        _make_response(tool_calls=[tc]),  # 重复
    ])
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=True, data={"temperature": 25.0})
    )

    resp = await mgr.chat_with_tools(AgentChatRequest(message="读温度"))
    assert resp.success
    assert resp.plan_steps == 2  # 第二次被检测到重复后停止，但 call_count 已经+1


@pytest.mark.asyncio
async def test_max_iterations_reached():
    """达到最大轮数 → 返回提示信息。"""
    mgr = _make_manager()
    tc = _make_tool_call("read_hardware", {"device_id": "HTHP-01"})

    # 每轮都返回不同的 tool_call（避免重复检测），但持续调用
    calls = []
    for i in range(9):
        calls.append(_make_response(tool_calls=[
            _make_tool_call("read_hardware", {"device_id": f"DEV-{i}"}, f"call_{i}")
        ]))
    mgr._llm.chat = AsyncMock(side_effect=calls)
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=True, data={})
    )

    resp = await mgr.chat_with_tools(AgentChatRequest(message="读所有设备"))
    assert resp.success
    assert "最大工具调用轮数" in resp.response


@pytest.mark.asyncio
async def test_tool_failure_returns_error():
    """工具执行失败 → LLM 被告知失败 → 给出解释。"""
    mgr = _make_manager()
    tc = _make_tool_call("read_hardware", {"device_id": "FAKE-01"})

    mgr._llm.chat = AsyncMock(side_effect=[
        _make_response(tool_calls=[tc]),
        _make_response(content="设备 FAKE-01 未找到"),
    ])
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=False, error="Device not found")
    )

    resp = await mgr.chat_with_tools(AgentChatRequest(message="读FAKE-01"))
    assert resp.success
    assert "未找到" in resp.response


@pytest.mark.asyncio
async def test_llm_timeout_returns_message():
    """LLM 调用超时 → 返回超时提示。"""
    mgr = _make_manager()

    # 直接 mock LLM 抛 TimeoutError，模拟 asyncio.wait_for 超时
    mgr._llm.chat = AsyncMock(side_effect=asyncio.TimeoutError())

    resp = await mgr.chat_with_tools(AgentChatRequest(message="你好"))
    assert resp.success
    assert "超时" in resp.response


@pytest.mark.asyncio
async def test_llm_exception_fallback():
    """LLM 调用抛异常 → 降级到无工具对话。"""
    mgr = _make_manager()

    # 第一次调用（带 tools）抛异常
    # 降级后的 _direct_chat 调用成功
    mgr._llm.chat = AsyncMock(side_effect=[
        Exception("tools not supported"),
        _make_response(content="直接回答的结果"),
    ])

    resp = await mgr.chat_with_tools(AgentChatRequest(message="你好"))
    assert resp.success
    assert "直接回答" in resp.response


# ---------------------------------------------------------------------------
# chat_stream_with_tools 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_no_tool():
    """流式对话：无工具 → 直接流式输出。"""
    mgr = _make_manager()
    mgr._llm.chat = AsyncMock(return_value=_make_response(content=""))
    mgr._llm.stream_chat = AsyncMock()

    # mock stream_chat 返回一个 chunk
    async def fake_stream(*args, **kwargs):
        chunk = MagicMock()
        chunk.delta = MagicMock(content="你好呀", role="assistant")
        yield chunk

    mgr._llm.stream_chat = fake_stream

    events = []
    async for event in mgr.chat_stream_with_tools(
        session_id="test-stream",
        message="你好",
    ):
        events.append(event)

    types = [e.type for e in events]
    assert "thinking" in types
    assert "chunk" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_with_tool():
    """流式对话：一次工具调用 → tools 事件 → 流式回答。"""
    mgr = _make_manager()
    tc = _make_tool_call("read_hardware", {"device_id": "HTHP-01"})

    # 第一次 chat 返回 tool_call，第二次返回无 tool_calls（触发流式阶段）
    mgr._llm.chat = AsyncMock(side_effect=[
        _make_response(tool_calls=[tc]),
        _make_response(content=""),  # 无 tool_calls → 进入 stream_chat
    ])
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=True, data={"temperature": 25.0})
    )

    async def fake_stream(*args, **kwargs):
        chunk = MagicMock()
        chunk.delta = MagicMock(content="温度25°C", role="assistant")
        yield chunk

    mgr._llm.stream_chat = fake_stream

    events = []
    async for event in mgr.chat_stream_with_tools(
        session_id="test-stream-tool",
        message="温度多少",
    ):
        events.append(event)

    types = [e.type for e in events]
    assert types.count("tools") >= 2  # start + complete
    assert "chunk" in types
    assert "done" in types
