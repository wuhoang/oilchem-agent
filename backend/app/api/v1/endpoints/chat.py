"""
Agent 对话端点。

提供 Agent 对话的 REST API 和流式 WebSocket 端点，
是前端与 Agent 交互的核心接口。

所有端点均经过输入护栏（Prompt 注入检测 / 敏感信息脱敏）和
输出护栏（有害内容过滤 / 敏感信息泄露防护）检查。
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.agent.manager import AgentManager, AgentStreamEvent
from app.agent.prompts import get_system_prompt
from app.guardrails.input_guard import InputGuardrail
from app.guardrails.output_guard import OutputGuardrail

router = APIRouter(tags=["chat"])

# 全局 Agent 管理器实例
_agent: AgentManager | None = None


def get_agent() -> AgentManager:
    """获取全局 Agent 管理器实例。"""
    global _agent
    if _agent is None:
        _agent = AgentManager()
    return _agent


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """对话请求。"""

    session_id: str | None = Field(default=None, description="会话 ID")
    message: str = Field(..., min_length=1, description="用户消息")
    system_prompt: str | None = Field(default=None, description="自定义系统提示词")
    temperature: float | None = Field(default=None, description="采样温度")
    context: str | None = Field(
        default=None,
        description="当前页面上下文（experiments/hardware/files/database/webform），"
        "决定加载的工具子集；None 表示全部",
    )


class ChatResponse(BaseModel):
    """对话响应。"""

    session_id: str = Field(..., description="会话 ID")
    response: str = Field(..., description="Agent 回复")
    plan_used: bool = Field(default=False, description="是否使用了规划")
    plan_steps: int = Field(default=0, description="规划步骤数")
    success: bool = Field(default=True, description="是否成功")
    error: str | None = Field(default=None, description="错误信息")
    execution_time_ms: int = Field(default=0, description="执行耗时")


class SessionResponse(BaseModel):
    """会话信息响应。"""

    session_id: str = Field(..., description="会话 ID")
    message_count: int = Field(default=0, description="消息数")
    has_summary: bool = Field(default=False, description="是否有摘要")
    title: str | None = Field(default=None, description="会话标题")
    created_at: float | None = Field(default=None, description="创建时间")
    updated_at: float | None = Field(default=None, description="更新时间")


# ---------------------------------------------------------------------------
# REST 端点
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """发送消息给 Agent，获取响应。

    支持多轮对话，通过 session_id 维持上下文。
    Agent 会自动规划任务、调用工具、维护记忆。

    安全：输入和输出均经过护栏检查。
    """
    # 输入护栏：Prompt 注入检测 + 敏感信息脱敏
    input_guard = InputGuardrail()
    guard_result = input_guard.check(request.message)
    if not guard_result["passed"]:
        logger.bind(component="chat").warning(
            "Input guardrail blocked message: {}", guard_result["reason"]
        )
        raise HTTPException(status_code=400, detail=guard_result["reason"])

    agent = get_agent()
    from app.agent.manager import AgentChatRequest

    result = await agent.chat_with_tools(
        AgentChatRequest(
            session_id=request.session_id,
            message=guard_result["sanitized_input"],
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            context=request.context,
        )
    )

    # 输出护栏：有害内容检测 + 敏感信息脱敏
    output_guard = OutputGuardrail()
    output_result = output_guard.check(result.response)
    if not output_result["passed"]:
        logger.bind(component="chat").warning(
            "Output guardrail blocked response: {}", output_result["reason"]
        )
        raise HTTPException(status_code=500, detail="Response filtered by safety guard")

    # 将脱敏后的输出写回
    sanitized = result.model_copy(update={"response": output_result["sanitized_output"]})

    logger.bind(component="chat").info(
        "Chat completed: session={}, plan_used={}, steps={}, time={}ms",
        result.session_id, result.plan_used, result.plan_steps, result.execution_time_ms,
    )
    return ChatResponse(**sanitized.model_dump())


@router.get("/chat/sessions")
async def list_sessions() -> dict:
    """列出所有会话。"""
    agent = get_agent()
    sessions = agent.list_sessions()
    return {"sessions": sessions}


@router.get("/chat/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """获取会话详情。"""
    agent = get_agent()
    info = agent.get_session_info(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return SessionResponse(**info)


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """删除会话。"""
    agent = get_agent()
    agent.delete_session(session_id)
    return {"success": True, "message": f"Session '{session_id}' deleted"}


# ---------------------------------------------------------------------------
# 流式端点
# ---------------------------------------------------------------------------

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """流式对话端点（SSE）。

    以 Server-Sent Events 方式推送 Agent 响应，
    支持实时显示 Agent 的规划过程、工具调用和流式输出。

    安全：输入经过护栏检查。流式内容在每个 chunk 产出时不做拦截
    （避免阻塞实时体验），在最终 done 事件汇总全文后记录审计日志。

    事件类型：
    - thinking: Agent 开始处理
    - tools: 工具调用过程（start/complete）
    - chunk: LLM 流式输出块
    - chart: 图表数据（base64 图片）
    - done: 对话完成
    - error: 错误

    工作流程：
    1. 输入护栏检查
    2. 流式 function calling 循环：模型自主决定调工具 / 给最终回答
    3. 工具结果以 role="tool" 消息回传，模型据此继续
    4. 最终回复阶段流式输出
    5. 结束时对完整输出执行输出护栏检查并记录审计日志
    """
    # 输入护栏：Prompt 注入检测 + 敏感信息脱敏
    input_guard = InputGuardrail()
    guard_result = input_guard.check(request.message)
    if not guard_result["passed"]:
        raise HTTPException(status_code=400, detail=guard_result["reason"])

    safe_message = guard_result["sanitized_input"]
    agent = get_agent()

    async def event_generator() -> AsyncIterator[str]:
        full_response = ""
        try:
            session_id = request.session_id or str(uuid.uuid4())
            system_prompt = request.system_prompt or get_system_prompt(
                context=request.context
            )

            # 1. 流式 function calling 对话
            #    事件序列：thinking → tools(start/complete) × N → chart(可选) → chunk → done
            async for event in agent.chat_stream_with_tools(
                session_id=session_id,
                message=safe_message,
                system_prompt=system_prompt,
                temperature=request.temperature,
                context=request.context,
            ):
                if event.type == "chunk" and event.content:
                    full_response += event.content
                elif event.type == "done" and event.content:
                    full_response = event.content
                yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"

            # 2. 输出护栏：对完整响应做安全审计（流式过程中不做拦截以保证实时体验）
            if full_response:
                output_guard = OutputGuardrail()
                output_check = output_guard.check(full_response)
                if not output_check["passed"]:
                    logger.bind(component="chat").warning(
                        "Stream output guardrail flagged content: session={}, reason={}",
                        session_id, output_check["reason"],
                    )
                else:
                    logger.bind(component="chat").info(
                        "Stream chat completed: session={}, response_len={}",
                        session_id, len(full_response),
                    )

        except Exception as exc:
            logger.bind(component="chat").error(
                "Stream chat error: session={}, error={}", session_id, exc
            )
            error_event = AgentStreamEvent(
                type="error",
                content=str(exc),
                data={"detail": str(exc)},
                done=True,
            )
            yield f"data: {json.dumps(error_event.model_dump(), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


__all__ = ["router"]
