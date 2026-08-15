"""
Agent 管理器。

将 Planner、Executor、Memory、LLM Client、Tool Manager 组装在一起，
提供 Agent 的主入口方法 chat()，处理完整的用户交互流程。
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

from loguru import logger
from pydantic import BaseModel, Field

from app.agent.executor import ExecutionResult, Executor, StepResult
from app.agent.memory import MemoryManager
from app.agent.planner import Plan, PlanStep, Planner
from app.agent.prompts import get_system_prompt
from app.llm import LLMClient, ChatMessage, MessageRole
from app.tools.base import ToolResult
from app.tools.manager import ToolManager


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class AgentChatRequest(BaseModel):
    """Agent 对话请求。"""

    session_id: str | None = Field(default=None, description="会话 ID（留空则自动生成）")
    message: str = Field(..., description="用户消息")
    system_prompt: str | None = Field(default=None, description="自定义系统提示词")
    temperature: float | None = Field(default=None, description="采样温度")


class AgentChatResponse(BaseModel):
    """Agent 对话响应。"""

    session_id: str = Field(..., description="会话 ID")
    response: str = Field(..., description="Agent 回复")
    plan_used: bool = Field(default=False, description="是否使用了规划")
    plan_steps: int = Field(default=0, description="规划步骤数")
    success: bool = Field(default=True, description="是否成功")
    error: str | None = Field(default=None, description="错误信息")
    execution_time_ms: int = Field(default=0, description="执行耗时")


class AgentStreamEvent(BaseModel):
    """Agent 流式对话事件（SSE）。"""

    type: str = Field(
        ...,
        description="事件类型：planning/tools/thinking/chunk/done/error",
    )
    session_id: str | None = Field(default=None, description="会话 ID")
    content: str | None = Field(default=None, description="事件文本内容")
    data: dict[str, Any] = Field(default_factory=dict, description="附加数据")
    done: bool = Field(default=False, description="是否为最终事件")


# ---------------------------------------------------------------------------
# Agent Manager
# ---------------------------------------------------------------------------

class AgentManager:
    """Agent 管理器。

    这是 Agent 系统的主入口，协调 LLM、Planner、Executor、Memory 和
    Tools 完成用户请求的端到端处理。

    Usage::

        agent = AgentManager()
        response = await agent.chat("读取 data.csv 并分析")
    """

    def __init__(self) -> None:
        self._llm = LLMClient.from_settings()
        self._tool_manager = ToolManager()
        self._memory = MemoryManager()
        self._planner = Planner(self._llm, self._tool_manager)
        self._executor = Executor(self._llm, self._tool_manager)
        self._max_tool_iterations = 8  # function calling 最大往返轮数，防死循环
        logger.bind(component="agent").info("AgentManager initialized")

    async def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        """处理用户对话请求。

        Parameters
        ----------
        request:
            对话请求。

        Returns
        -------
        AgentChatResponse
            对话响应。
        """
        start = time.perf_counter()

        # 1. 确定会话 ID
        session_id = request.session_id or str(uuid.uuid4())

        # 2. 获取上下文
        context = self._memory.get_context(session_id)

        # 3. 添加用户消息到记忆
        self._memory.add_message(
            session_id, MessageRole.USER, request.message
        )

        # 4. 获取系统提示词
        system_prompt = request.system_prompt or get_system_prompt()

        try:
            # 5. 规划
            plan = await self._planner.plan(
                request.message, context, system_prompt
            )

            # 如果不需要工具（纯对话），直接 LLM 回复
            if not plan.steps and not plan.needs_clarification:
                response = await self._direct_chat(
                    request.message, context, system_prompt, request.temperature
                )
                self._memory.add_message(
                    session_id, MessageRole.ASSISTANT, response
                )
                elapsed = int((time.perf_counter() - start) * 1000)
                return AgentChatResponse(
                    session_id=session_id,
                    response=response,
                    plan_used=False,
                    plan_steps=0,
                    success=True,
                    execution_time_ms=elapsed,
                )

            # 如果需要澄清
            if plan.needs_clarification:
                self._memory.add_message(
                    session_id,
                    MessageRole.ASSISTANT,
                    plan.clarification_question or "需要更多信息。",
                )
                elapsed = int((time.perf_counter() - start) * 1000)
                return AgentChatResponse(
                    session_id=session_id,
                    response=plan.clarification_question or "需要更多信息。",
                    plan_used=True,
                    plan_steps=len(plan.steps),
                    success=False,
                    error="needs_clarification",
                    execution_time_ms=elapsed,
                )

            # 6. 执行规划
            result = await self._executor.execute(plan)

            # 7. 记录结果
            self._memory.add_message(
                session_id,
                MessageRole.ASSISTANT,
                result.final_response,
            )

            # 8. 存储长期知识
            if result.success:
                self._memory.add_knowledge(
                    f"Q: {request.message[:100]}\nA: {result.final_response[:200]}",
                    source=f"session:{session_id}",
                )

            elapsed = int((time.perf_counter() - start) * 1000)
            return AgentChatResponse(
                session_id=session_id,
                response=result.final_response,
                plan_used=True,
                plan_steps=len(plan.steps),
                success=result.success,
                execution_time_ms=elapsed,
            )

        except Exception as exc:
            logger.bind(component="agent").error(
                "Chat failed for session {}: {}", session_id, exc
            )
            elapsed = int((time.perf_counter() - start) * 1000)
            return AgentChatResponse(
                session_id=session_id,
                response=f"Agent error: {exc}",
                success=False,
                error=str(exc),
                execution_time_ms=elapsed,
            )

    # -- function calling 主链路 -----------------------------------------------------------

    async def chat_with_tools(
        self,
        request: AgentChatRequest,
    ) -> AgentChatResponse:
        """原生 function calling 对话（同步主入口）。

        模型直接输出结构化 tool_calls，工具结果以 role="tool" 消息回传，
        模型自主决定继续调用 / 重试 / 给出最终回答。替代旧的
        Planner(手写 JSON 计划) → Executor 链路。

        工具往返只在当次循环内有效，不写入 Memory（避免污染多轮对话）。
        """
        start = time.perf_counter()
        session_id = request.session_id or str(uuid.uuid4())

        self._memory.add_message(session_id, MessageRole.USER, request.message)

        system_prompt = request.system_prompt or get_system_prompt()
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.extend(self._memory.get_context(session_id))

        tools = self._tool_manager.list_tools_schema()

        final_response = ""
        tool_called = False
        call_count = 0
        skip_memory = False
        try:
            for _ in range(self._max_tool_iterations):
                # 工具决策用非流式，规避流式 tool_calls 增量解析的复杂度
                try:
                    response = await self._llm.chat(
                        messages,
                        temperature=request.temperature or 0.7,
                        max_tokens=4096,
                        tools=tools,
                    )
                except Exception:
                    # 降级：provider 不支持 tools 时，走单轮无工具对话
                    logger.bind(component="agent").warning(
                        "tools 请求失败，降级为无工具对话: session={}", session_id
                    )
                    fallback = await self._direct_chat(
                        request.message,
                        self._memory.get_context(session_id),
                        system_prompt,
                        request.temperature,
                    )
                    final_response = fallback
                    break

                if not response.choices:
                    break

                msg = response.choices[0].message

                # 无 tool_calls → 最终回答
                if not msg.tool_calls:
                    final_response = msg.content or ""
                    break

                # 有 tool_calls → 执行工具
                tool_called = True
                messages.append(
                    ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=msg.content or "",
                        tool_calls=msg.tool_calls,
                    )
                )
                for tc in msg.tool_calls:
                    call_count += 1
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    logger.bind(component="agent").info(
                        "Agent tool call #{}/{}: {} args={}",
                        call_count, self._max_tool_iterations, tool_name, args,
                    )
                    tool_result = await self._tool_manager.execute(tool_name, **args)
                    messages.append(
                        ChatMessage(
                            role=MessageRole.TOOL,
                            content=self._serialize_tool_result(tool_result),
                            tool_call_id=tc.get("id", ""),
                        )
                    )
            else:
                # 达到最大轮数仍未收敛
                final_response = "已达到最大工具调用轮数，任务未能完成，请重试或换一种问法。"
                skip_memory = True
                logger.bind(component="agent").warning(
                    "Tool loop hit max iterations: session={}", session_id
                )

        except Exception as exc:
            logger.bind(component="agent").error(
                "Chat with tools failed for session {}: {}", session_id, exc
            )
            elapsed = int((time.perf_counter() - start) * 1000)
            return AgentChatResponse(
                session_id=session_id,
                response=f"Agent error: {exc}",
                success=False,
                error=str(exc),
                execution_time_ms=elapsed,
            )

        # 记录 assistant 回复到记忆（系统提示类跳过，避免污染后续对话）
        if final_response and not skip_memory:
            self._memory.add_message(session_id, MessageRole.ASSISTANT, final_response)

        elapsed = int((time.perf_counter() - start) * 1000)
        return AgentChatResponse(
            session_id=session_id,
            response=final_response,
            plan_used=tool_called,
            plan_steps=call_count,
            success=True,
            execution_time_ms=elapsed,
        )

    # -- 会话管理 -----------------------------------------------------------

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """获取会话信息。"""
        session = self._memory.get_session(session_id)
        if session is None:
            return None

        title = self._extract_title(session)
        return {
            "session_id": session.session_id,
            "message_count": len(session.messages),
            "has_summary": bool(session.summary),
            "title": title,
            "created_at": session.messages[0].timestamp if session.messages else None,
            "updated_at": session.messages[-1].timestamp if session.messages else None,
        }

    @staticmethod
    def _extract_title(session: Any) -> str:
        """从会话的第一条用户消息中提取标题。"""
        if not session.messages:
            return ""
        for msg in session.messages:
            if msg.role.value == "user":
                text = msg.content.strip()
                if len(text) > 30:
                    return text[:30] + "..."
                return text
        return ""

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话。"""
        sessions = []
        for sid in self._memory.list_sessions():
            info = self.get_session_info(sid)
            if info:
                sessions.append(info)
        sessions.sort(key=lambda s: s.get("updated_at") or 0, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> None:
        """删除会话。"""
        self._memory.delete_session(session_id)

    # -- 规划与执行 -----------------------------------------------------------

    async def plan(
        self,
        message: str,
        session_id: str,
        system_prompt: str | None = None,
    ) -> Plan:
        """为用户消息生成规划。

        Parameters
        ----------
        message:
            用户消息。
        session_id:
            会话 ID。
        system_prompt:
            自定义系统提示词。

        Returns
        -------
        Plan
            规划结果。
        """
        context = self._memory.get_context(session_id)
        prompt = system_prompt or get_system_prompt()
        return await self._planner.plan(message, context, prompt)

    async def execute_plan(self, plan: Plan) -> ExecutionResult:
        """执行完整规划。

        Parameters
        ----------
        plan:
            要执行的规划。

        Returns
        -------
        ExecutionResult
            执行结果。
        """
        return await self._executor.execute(plan)

    async def execute_step(
        self, step: PlanStep, context: dict[str, Any] | None = None
    ) -> StepResult:
        """执行单个规划步骤。

        Parameters
        ----------
        step:
            要执行的步骤。
        context:
            步骤上下文（前序步骤结果）。

        Returns
        -------
        StepResult
            步骤执行结果。
        """
        return await self._executor._execute_step(step, context or {})

    # -- 流式对话 -----------------------------------------------------------

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        plan: Plan,
        system_prompt: str | None = None,
        temperature: float | None = None,
        step_results: list[StepResult] | None = None,
    ) -> AsyncIterator[AgentStreamEvent]:
        """流式对话（真正的 LLM 流式调用）。

        在流式输出前先推送 "thinking" 事件展示规划步骤，
        如果有工具执行结果（step_results），会把结果作为工具消息注入上下文，
        让 LLM 基于真实执行结果生成回复，而不是输出"我将调用工具"的原始文本。

        Parameters
        ----------
        session_id:
            会话 ID。
        message:
            用户消息。
        plan:
            预先生成的规划对象。
        system_prompt:
            自定义系统提示词。
        temperature:
            采样温度。
        step_results:
            已执行的工具步骤结果（可选）。

        Yields
        ------
        AgentStreamEvent
            流式事件。
        """
        self._memory.add_message(session_id, MessageRole.USER, message)

        yield AgentStreamEvent(
            type="thinking",
            session_id=session_id,
            content=self._build_thinking_content(plan, step_results),
            data={
                "plan_goal": plan.goal,
                "plan_steps": [s.model_dump() for s in plan.steps],
            },
            done=False,
        )

        # 构造消息序列
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)
            )
        context = self._memory.get_context(session_id)
        messages.extend(context)

        # 如果有工具执行结果，把结果摘要与用户问题合并为最后一条 USER 消息，
        # 避免出现 USER / USER 连续的角色序列（部分 LLM 会拒绝）。
        final_user_content = message
        if step_results:
            tool_summary = self._build_tool_summary(plan, step_results)
            final_user_content = (
                f"[以下是我刚刚通过工具获取/执行的结果，请基于这些结果直接回答用户问题，"
                f"不要在回复中提到 '我将调用工具' 或规划步骤等内部细节]\n\n"
                f"{tool_summary}\n\n"
                f"--- 用户原始问题 ---\n{message}"
            )

        messages.append(ChatMessage(role=MessageRole.USER, content=final_user_content))

        full_response = ""
        async for chunk in self._llm.stream_chat(
            messages,
            temperature=temperature or 0.7,
            max_tokens=4096,
        ):
            if chunk.delta.content:
                full_response += chunk.delta.content
                yield AgentStreamEvent(
                    type="chunk",
                    session_id=session_id,
                    content=chunk.delta.content,
                    done=False,
                )

        self._memory.add_message(
            session_id, MessageRole.ASSISTANT, full_response
        )

        yield AgentStreamEvent(
            type="done",
            session_id=session_id,
            content=full_response,
            data={
                "plan_used": bool(plan.steps),
                "plan_steps": len(plan.steps),
                "success": True,
            },
            done=True,
        )

    async def chat_stream_with_tools(
        self,
        session_id: str,
        message: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[AgentStreamEvent]:
        """流式 function calling 对话（SSE 主入口）。

        事件序列：
          thinking → tools(start/complete) × N → chart(可选) → chunk × M → done

        工具决策阶段用非流式 chat（返回完整 tool_calls，规避流式增量解析），
        最终回复阶段用流式 stream_chat（打字机效果）。
        """
        self._memory.add_message(session_id, MessageRole.USER, message)

        yield AgentStreamEvent(
            type="thinking",
            session_id=session_id,
            content="正在分析你的请求...",
            data={"goal": message},
            done=False,
        )

        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.extend(self._memory.get_context(session_id))

        tools = self._tool_manager.list_tools_schema()
        tool_desc_map = {t["name"]: t["description"] for t in self._tool_manager.list_available_tools()}

        tool_called = False
        call_count = 0
        final_response = ""
        skip_memory = False

        try:
            for _ in range(self._max_tool_iterations):
                try:
                    response = await self._llm.chat(
                        messages,
                        temperature=temperature or 0.7,
                        max_tokens=4096,
                        tools=tools,
                    )
                except Exception:
                    # 降级：provider 不支持 tools，走无工具对话
                    logger.bind(component="agent").warning(
                        "tools 请求失败，降级为无工具对话: session={}", session_id
                    )
                    break

                if not response.choices:
                    break

                msg = response.choices[0].message

                # 无 tool_calls → 进入最终流式回复阶段
                if not msg.tool_calls:
                    break

                tool_called = True
                messages.append(
                    ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=msg.content or "",
                        tool_calls=msg.tool_calls,
                    )
                )
                for tc in msg.tool_calls:
                    call_count += 1
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    # tools start 事件
                    yield AgentStreamEvent(
                        type="tools",
                        session_id=session_id,
                        data={
                            "call_index": call_count,
                            "action": "start",
                            "tool_name": tool_name,
                            "description": tool_desc_map.get(tool_name, tool_name),
                        },
                        done=False,
                    )

                    tool_result = await self._tool_manager.execute(tool_name, **args)

                    # 序列化后作为 tool 消息回传
                    messages.append(
                        ChatMessage(
                            role=MessageRole.TOOL,
                            content=self._serialize_tool_result(tool_result),
                            tool_call_id=tc.get("id", ""),
                        )
                    )

                    # tools complete 事件
                    output_preview = ""
                    if tool_result.data is not None:
                        try:
                            output_preview = str(tool_result.data)[:500]
                        except Exception:
                            output_preview = ""
                    yield AgentStreamEvent(
                        type="tools",
                        session_id=session_id,
                        data={
                            "call_index": call_count,
                            "action": "complete",
                            "success": tool_result.success,
                            "tool_name": tool_name,
                            "output": output_preview or None,
                            "error": tool_result.error,
                        },
                        done=False,
                    )

                    # 检测图表数据：base64 图片走 chart 事件，不进 LLM 上下文
                    if tool_result.success and isinstance(tool_result.data, dict):
                        if "image_base64" in tool_result.data:
                            yield AgentStreamEvent(
                                type="chart",
                                session_id=session_id,
                                data={
                                    "call_index": call_count,
                                    "chart_type": tool_result.data.get("chart_type", "plot"),
                                    "image_base64": tool_result.data["image_base64"],
                                    "image_mime": tool_result.data.get("image_mime", "image/png"),
                                    "width": tool_result.data.get("width", 800),
                                    "height": tool_result.data.get("height", 500),
                                },
                                done=False,
                            )
            else:
                final_response = "已达到最大工具调用轮数，任务未能完成，请重试或换一种问法。"
                skip_memory = True
                logger.bind(component="agent").warning(
                    "Tool loop hit max iterations: session={}", session_id
                )

            # 最终回复：流式输出（打字机效果）
            if not final_response:
                async for chunk in self._llm.stream_chat(
                    messages,
                    temperature=temperature or 0.7,
                    max_tokens=4096,
                ):
                    if chunk.delta.content:
                        final_response += chunk.delta.content
                        yield AgentStreamEvent(
                            type="chunk",
                            session_id=session_id,
                            content=chunk.delta.content,
                            done=False,
                        )

        except Exception as exc:
            logger.bind(component="agent").error(
                "Stream chat with tools failed for session {}: {}", session_id, exc
            )
            yield AgentStreamEvent(
                type="error",
                session_id=session_id,
                content=str(exc),
                data={"detail": str(exc)},
                done=True,
            )
            return

        if final_response and not skip_memory:
            self._memory.add_message(session_id, MessageRole.ASSISTANT, final_response)

        yield AgentStreamEvent(
            type="done",
            session_id=session_id,
            content=final_response,
            data={
                "plan_used": tool_called,
                "plan_steps": call_count,
                "success": True,
            },
            done=True,
        )

    # -- 内部方法 -----------------------------------------------------------

    @staticmethod
    def _build_thinking_content(
        plan: Plan,
        step_results: list[StepResult] | None = None,
    ) -> str:
        """构建 thinking 事件的文本内容。"""
        lines = [f"目标: {plan.goal}"]
        if plan.steps:
            lines.append("计划步骤:")
            for step in plan.steps:
                tool_info = f" → [{step.tool_name}]" if step.tool_name else ""
                lines.append(f"  {step.step_id}. {step.description}{tool_info}")
        else:
            lines.append("无需工具调用，直接回复。")

        if step_results:
            lines.append("")
            lines.append("执行进展:")
            for sr in step_results:
                status = "✓" if sr.success else "✗"
                output_preview = ""
                if sr.output:
                    try:
                        output_str = str(sr.output)
                        output_preview = f" - {output_str[:80]}{'...' if len(output_str) > 80 else ''}"
                    except Exception:
                        output_preview = ""
                lines.append(
                    f"  {status} 步骤 {sr.step_id} [{sr.tool_called or 'llm'}]{output_preview}"
                )
        return "\n".join(lines)

    @staticmethod
    def _build_tool_summary(
        plan: Plan, step_results: list[StepResult]
    ) -> str:
        """把工具执行结果拼成一段可读摘要，注入给 LLM。"""
        parts = [f"[执行结果摘要] 共 {len(step_results)} 步\n"]
        for sr in step_results:
            status = "成功" if sr.success else "失败"
            parts.append(f"--- 步骤 {sr.step_id} [{status}] 工具: {sr.tool_called or 'llm'} ---")
            if sr.success:
                output_str = AgentManager._sanitize_tool_output(sr.output)
                if len(output_str) > 3000:
                    output_str = output_str[:3000] + "\n... (内容已截断)"
                parts.append(output_str)
            else:
                parts.append(f"错误: {sr.error}")
            parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _sanitize_tool_output(output: Any) -> str:
        """将工具输出转换为 LLM 可读的摘要文本。

        对包含 base64 图片的字典，替换为简短描述，避免 token 浪费。
        """
        if isinstance(output, dict) and "image_base64" in output:
            chart_type = output.get("chart_type", "unknown")
            width = output.get("width", "?")
            height = output.get("height", "?")
            mime = output.get("image_mime", "image/png")
            return (
                f"✅ 图表已成功生成并在前端页面展示！\n"
                f"   图表类型: {chart_type}\n"
                f"   图片格式: {mime}\n"
                f"   图片尺寸: {width}×{height} 像素\n"
                f"   (图片数据已省略，已在对话中以可视化方式呈现)"
            )
        try:
            output_str = str(output)
        except Exception:
            output_str = repr(output)
        return output_str

    @staticmethod
    def _serialize_tool_result(result: ToolResult) -> str:
        """把工具执行结果序列化为回传给 LLM 的 tool 消息内容。

        含 base64 图片的字典走 _sanitize_tool_output 变成文字描述
        （图片已通过 SSE chart 事件给前端，LLM 不需要图片数据），
        普通数据 JSON 序列化并截断，避免 token 爆炸。
        """
        if not result.success:
            return f"工具执行失败: {result.error}"

        data = result.data
        if isinstance(data, dict) and "image_base64" in data:
            return AgentManager._sanitize_tool_output(data)

        try:
            text = json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            text = str(data)
        if len(text) > 3000:
            text = text[:3000] + "\n...(内容已截断)"
        return text

    async def _direct_chat(
        self,
        message: str,
        context: list[ChatMessage],
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """直接对话（不需要规划工具时使用）。"""
        messages = []
        if system_prompt:
            messages.append(
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)
            )
        messages.extend(context)
        messages.append(ChatMessage(role=MessageRole.USER, content=message))

        response = await self._llm.chat(
            messages,
            temperature=temperature or 0.7,
            max_tokens=2048,
        )

        if response.choices:
            return response.choices[0].message.content
        return "I'm not sure how to respond to that."


__all__ = [
    "AgentChatRequest",
    "AgentChatResponse",
    "AgentStreamEvent",
    "AgentManager",
]
