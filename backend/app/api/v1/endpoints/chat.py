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

    result = await agent.chat(
        AgentChatRequest(
            session_id=request.session_id,
            message=guard_result["sanitized_input"],
            system_prompt=request.system_prompt,
            temperature=request.temperature,
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
    - planning: 规划结果
    - tools: 工具调用过程
    - thinking: Agent 思考过程（含执行进展）
    - chunk: LLM 流式输出块
    - chart: 图表数据（base64 图片）
    - done: 对话完成
    - error: 错误

    工作流程：
    1. 输入护栏检查
    2. 生成规划（plan）
    3. 推送 planning 事件（展示规划步骤）
    4. 逐步执行规划中的工具步骤，每步推送 tools start/complete
    5. 把所有工具执行结果作为 "tool" 消息注入 LLM 上下文
    6. 调用 chat_stream 让 LLM 基于真实执行结果流式输出自然语言回复
    7. 结束时对完整输出执行输出护栏检查并记录审计日志
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
            system_prompt = request.system_prompt or get_system_prompt()

            # 1. 生成规划
            plan = await agent.plan(
                safe_message, session_id, system_prompt
            )

            # 安全上限：超过 8 步时只保留前 8 步，避免过长的链式调用
            if len(plan.steps) > 8:
                plan = plan.model_copy(
                    update={"steps": plan.steps[:8]}
                )

            # 推送 planning 事件
            planning_event = AgentStreamEvent(
                type="planning",
                session_id=session_id,
                data={
                    "goal": plan.goal,
                    "steps": [s.model_dump() for s in plan.steps],
                    "needs_clarification": plan.needs_clarification,
                    "clarification_question": plan.clarification_question,
                },
                done=False,
            )
            yield f"data: {json.dumps(planning_event.model_dump(), ensure_ascii=False)}\n\n"

            # 2. 处理需要澄清的情况
            if plan.needs_clarification:
                clarification_event = AgentStreamEvent(
                    type="done",
                    session_id=session_id,
                    content=plan.clarification_question
                    or "需要更多信息。",
                    data={"success": False, "reason": "needs_clarification"},
                    done=True,
                )
                yield f"data: {json.dumps(clarification_event.model_dump(), ensure_ascii=False)}\n\n"
                return

            # 3. 逐步执行规划中的工具步骤
            step_results = []
            if plan.steps:
                step_context: dict = {}
                for step in plan.steps:
                    step_id = step.step_id

                    # 推送工具开始事件
                    tool_start_event = AgentStreamEvent(
                        type="tools",
                        session_id=session_id,
                        data={
                            "step_id": step_id,
                            "action": "start",
                            "description": step.description,
                            "tool_name": step.tool_name,
                        },
                        done=False,
                    )
                    yield f"data: {json.dumps(tool_start_event.model_dump(), ensure_ascii=False)}\n\n"

                    # 执行步骤
                    step_result = await agent.execute_step(
                        step, step_context
                    )
                    step_results.append(step_result)

                    # 更新上下文供后续步骤使用
                    step_context[f"step_{step_id}_result"] = (
                        step_result.output
                    )

                    # 推送工具完成事件
                    output_preview = ""
                    if step_result.output is not None:
                        try:
                            output_str = str(step_result.output)
                            output_preview = output_str[:500]
                        except Exception:
                            output_preview = ""
                    tool_done_event = AgentStreamEvent(
                        type="tools",
                        session_id=session_id,
                        data={
                            "step_id": step_id,
                            "action": "complete",
                            "success": step_result.success,
                            "tool_name": step.tool_name,
                            "output": output_preview or None,
                            "error": step_result.error,
                        },
                        done=False,
                    )
                    yield f"data: {json.dumps(tool_done_event.model_dump(), ensure_ascii=False)}\n\n"

                    # 检测图表数据：如果工具返回了 image_base64，发送 chart 事件
                    if step_result.success and isinstance(step_result.output, dict):
                        if "image_base64" in step_result.output:
                            chart_event = AgentStreamEvent(
                                type="chart",
                                session_id=session_id,
                                data={
                                    "step_id": step_id,
                                    "chart_type": step_result.output.get("chart_type", "plot"),
                                    "image_base64": step_result.output["image_base64"],
                                    "image_mime": step_result.output.get("image_mime", "image/png"),
                                    "width": step_result.output.get("width", 800),
                                    "height": step_result.output.get("height", 500),
                                },
                                done=False,
                            )
                            yield f"data: {json.dumps(chart_event.model_dump(), ensure_ascii=False)}\n\n"

            # 4. 调用 agent.chat_stream 进行真正的 LLM 流式输出
            #    把 step_results 注入，让 LLM 基于真实执行结果生成自然语言总结
            async for event in agent.chat_stream(
                session_id=session_id,
                message=safe_message,
                plan=plan,
                system_prompt=system_prompt,
                temperature=request.temperature,
                step_results=step_results,
            ):
                if event.type == "chunk" and event.content:
                    full_response += event.content
                elif event.type == "done" and event.content:
                    full_response = event.content
                yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"

            # 5. 输出护栏：对完整响应做安全审计（流式过程中不做拦截以保证实时体验）
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
                        "Stream chat completed: session={}, plan_steps={}, response_len={}",
                        session_id, len(plan.steps), len(full_response),
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
