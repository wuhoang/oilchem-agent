"""
Agent 执行器。

按计划步骤逐步执行，支持工具调用、步骤间结果传递、
以及在每步执行后调用 LLM 进行反思和调整。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.agent.planner import Plan, PlanStep
from app.llm import LLMClient, ChatMessage, MessageRole
from app.tools.manager import ToolManager


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class StepResult(BaseModel):
    """单步执行结果。"""

    step_id: int = Field(..., description="步骤序号")
    success: bool = Field(..., description="是否成功")
    output: Any = Field(default=None, description="执行输出")
    error: str | None = Field(default=None, description="错误信息")
    tool_called: str | None = Field(default=None, description="调用的工具名")
    thought: str = Field(default="", description="Agent 思考过程")


class ExecutionResult(BaseModel):
    """完整执行结果。"""

    plan: Plan = Field(..., description="执行的规划")
    step_results: list[StepResult] = Field(default_factory=list, description="各步骤结果")
    final_response: str = Field(default="", description="最终给用户的回复")
    success: bool = Field(default=True, description="整体是否成功")


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class Executor:
    """计划执行器。

    逐步执行 Plan 中的每个步骤，处理工具调用和结果汇总。

    Usage::

        executor = Executor(llm_client, tool_manager)
        result = await executor.execute(plan)
    """

    def __init__(self, llm_client: LLMClient, tool_manager: ToolManager) -> None:
        self._llm = llm_client
        self._tool_manager = tool_manager
        self._max_retries_per_step = 2
        logger.bind(component="executor").info("Executor initialized")

    async def execute(self, plan: Plan) -> ExecutionResult:
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
        step_results: list[StepResult] = []
        context: dict[str, Any] = {}

        if plan.needs_clarification:
            return ExecutionResult(
                plan=plan,
                step_results=[],
                final_response=plan.clarification_question or "I need clarification.",
                success=False,
            )

        for step in plan.steps:
            logger.bind(component="executor").info(
                "Executing step {}: {}", step.step_id, step.description[:80]
            )

            result = await self._execute_step(step, context)
            step_results.append(result)

            # 将结果存入上下文供后续步骤使用
            context[f"step_{step.step_id}_result"] = result.output

            if not result.success:
                logger.bind(component="executor").warning(
                    "Step {} failed: {}", step.step_id, result.error
                )
                # 失败后用 LLM 决定是否继续
                should_continue = await self._should_continue(step, result, plan)
                if not should_continue:
                    return ExecutionResult(
                        plan=plan,
                        step_results=step_results,
                        final_response=f"Task stopped at step {step.step_id}: {result.error}",
                        success=False,
                    )

        # 生成最终回复
        final_response = await self._generate_final_response(plan, step_results)

        return ExecutionResult(
            plan=plan,
            step_results=step_results,
            final_response=final_response,
            success=True,
        )

    # -- 内部方法 -----------------------------------------------------------

    async def _execute_step(
        self, step: PlanStep, context: dict[str, Any]
    ) -> StepResult:
        """执行单个步骤。"""
        # 如果没有工具，直接让 LLM 处理
        if not step.tool_name:
            return await self._execute_llm_step(step, context)

        # 执行工具调用（解析上下文引用，如 {step_1_result.values}）
        tool_args = self._resolve_tool_args(step.tool_args, context)

        try:
            result = await self._tool_manager.execute(step.tool_name, **tool_args)
            return StepResult(
                step_id=step.step_id,
                success=result.success,
                output=result.data,
                error=result.error,
                tool_called=step.tool_name,
                thought=step.description,
            )
        except Exception as exc:
            logger.bind(component="executor").error(
                "Tool execution failed: {}", exc
            )
            return StepResult(
                step_id=step.step_id,
                success=False,
                output=None,
                error=str(exc),
                tool_called=step.tool_name,
            )

    async def _execute_llm_step(
        self, step: PlanStep, context: dict[str, Any]
    ) -> StepResult:
        """执行纯 LLM 步骤（无工具调用）。"""
        context_str = self._format_context(context)
        messages = [
            ChatMessage(
                role=MessageRole.USER,
                content=f"""Step: {step.description}

Context so far:
{context_str}

Please complete this step and provide the result.""",
            )
        ]

        try:
            response = await self._llm.chat(messages, max_tokens=2048)
            if response.choices:
                return StepResult(
                    step_id=step.step_id,
                    success=True,
                    output=response.choices[0].message.content,
                    thought=step.description,
                )
            return StepResult(
                step_id=step.step_id,
                success=False,
                output=None,
                error="LLM returned no choices",
            )
        except Exception as exc:
            return StepResult(
                step_id=step.step_id,
                success=False,
                output=None,
                error=str(exc),
            )

    async def _should_continue(
        self, failed_step: PlanStep, result: StepResult, plan: Plan
    ) -> bool:
        """决定是否在步骤失败后继续。"""
        messages = [
            ChatMessage(
                role=MessageRole.USER,
                content=f"""Step {failed_step.step_id} failed:
Description: {failed_step.description}
Error: {result.error}

Should the plan continue or stop? Answer with YES or NO only.""",
            )
        ]
        try:
            response = await self._llm.chat(messages, max_tokens=50)
            if response.choices:
                answer = response.choices[0].message.content.strip().upper()
                return "YES" in answer
        except Exception:
            pass
        return False  # 默认停止

    async def _generate_final_response(
        self, plan: Plan, step_results: list[StepResult]
    ) -> str:
        """生成最终回复。"""
        results_summary = []
        for sr in step_results:
            status = "✓" if sr.success else "✗"
            output_str = str(sr.output)[:200] if sr.output else "(no output)"
            results_summary.append(
                f"Step {sr.step_id} [{status}]: {output_str}"
            )

        messages = [
            ChatMessage(
                role=MessageRole.USER,
                content=f"""User goal: {plan.goal}

Execution results:
{chr(10).join(results_summary)}

Please provide a concise, user-friendly summary of what was accomplished.
If any steps failed, explain what could be done.""",
            )
        ]

        try:
            response = await self._llm.chat(messages, max_tokens=2048)
            if response.choices:
                return response.choices[0].message.content
        except Exception as exc:
            logger.bind(component="executor").error(
                "Final response generation failed: {}", exc
            )

        # 降级：直接拼接结果
        return self._fallback_response(step_results)

    @staticmethod
    def _resolve_tool_args(
        tool_args: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """解析工具参数中的上下文引用。

        支持两种格式：
          - {step_N_result} 整体引用，转成字符串
          - {step_N_result.字段} 点路径引用，从 dict 中提取对应值（保留原始类型）
        """
        resolved = {}
        for key, value in tool_args.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                ref = value[1:-1]
                ref_key, *path = ref.split(".")
                if ref_key in context:
                    obj = context[ref_key]
                    for part in path:
                        if isinstance(obj, dict) and part in obj:
                            obj = obj[part]
                        else:
                            obj = None
                            break
                    if obj is not None and path:
                        resolved[key] = obj
                    else:
                        resolved[key] = str(context[ref_key])
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _format_context(context: dict[str, Any]) -> str:
        """格式化上下文为可读字符串。"""
        if not context:
            return "(no previous results)"
        lines = []
        for key, value in context.items():
            val_str = str(value)[:100] if value else "None"
            lines.append(f"  {key}: {val_str}")
        return "\n".join(lines)

    @staticmethod
    def _fallback_response(step_results: list[StepResult]) -> str:
        """降级响应：直接拼接步骤结果。"""
        parts = []
        for sr in step_results:
            status = "成功" if sr.success else "失败"
            output_str = str(sr.output)[:200] if sr.output else ""
            parts.append(f"步骤 {sr.step_id} [{status}]: {output_str}")
        return "\n".join(parts)


__all__ = [
    "StepResult",
    "ExecutionResult",
    "Executor",
]
