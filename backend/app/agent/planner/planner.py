"""
Agent 规划模块。

负责将用户请求拆解为一系列可执行的步骤（Plan），
每个步骤包含要调用的工具和参数。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.llm import LLMClient, ChatMessage, MessageRole
from app.tools.manager import ToolManager


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class PlanStep(BaseModel):
    """规划步骤。"""

    step_id: int = Field(..., description="步骤序号")
    description: str = Field(..., description="步骤描述")
    tool_name: str | None = Field(default=None, description="要调用的工具名称")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="工具参数")
    expected_output: str = Field(default="", description="预期输出描述")


class Plan(BaseModel):
    """完整规划。"""

    goal: str = Field(..., description="用户目标")
    steps: list[PlanStep] = Field(default_factory=list, description="步骤列表")
    needs_clarification: bool = Field(
        default=False, description="是否需要向用户确认"
    )
    clarification_question: str | None = Field(
        default=None, description="需要用户澄清的问题"
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class Planner:
    """任务规划器。

    使用 LLM 将用户请求拆解为可执行的步骤序列。

    Usage::

        planner = Planner(llm_client, tool_manager)
        plan = await planner.plan("读取 data.csv 并分析数据趋势")
    """

    def __init__(self, llm_client: LLMClient, tool_manager: ToolManager) -> None:
        self._llm = llm_client
        self._tool_manager = tool_manager
        logger.bind(component="planner").info("Planner initialized")

    async def plan(
        self,
        user_input: str,
        context: list[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> Plan:
        """规划用户请求。

        Parameters
        ----------
        user_input:
            用户输入。
        context:
            对话历史上下文。
        system_prompt:
            系统提示词。

        Returns
        -------
        Plan
            规划结果。
        """
        available_tools = self._tool_manager.list_available_tools()
        tools_desc = self._format_tools_description(available_tools)

        messages = []
        if system_prompt:
            messages.append(
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)
            )
        if context:
            messages.extend(context)

        # 规划提示词
        planning_prompt = self._build_planning_prompt(
            user_input, tools_desc
        )
        messages.append(
            ChatMessage(role=MessageRole.USER, content=planning_prompt)
        )

        logger.bind(component="planner").debug(
            "Planning for: {}", user_input[:100]
        )

        try:
            response = await self._llm.chat(
                messages,
                temperature=0.3,
                max_tokens=4096,
            )

            if not response.choices:
                return Plan(
                    goal=user_input,
                    steps=[],
                    needs_clarification=True,
                    clarification_question="无法生成规划，请重试。",
                )

            llm_output = response.choices[0].message.content
            plan = self._parse_llm_plan(llm_output, user_input)

            logger.bind(component="planner").info(
                "Plan generated: {} steps for '{}'",
                len(plan.steps),
                user_input[:50],
            )
            return plan

        except Exception as exc:
            logger.bind(component="planner").error(
                "Planning failed: {}", exc
            )
            return Plan(
                goal=user_input,
                steps=[],
                needs_clarification=True,
                clarification_question=f"规划失败：{exc}",
            )

    # -- 内部方法 -----------------------------------------------------------

    @staticmethod
    def _format_tools_description(tools: list[dict]) -> str:
        """格式化工具描述，供 LLM 理解。"""
        if not tools:
            return "No tools available."

        lines = ["Available tools:"]
        for tool in tools:
            lines.append(f"  - {tool['name']}: {tool['description']}")
            if tool.get("parameters"):
                lines.append(f"    Parameters: {json.dumps(tool['parameters'], indent=6)}")
        return "\n".join(lines)

    @staticmethod
    def _build_planning_prompt(user_input: str, tools_desc: str) -> str:
        """构建规划提示词。"""
        return f"""请为以下用户请求创建一个详细的执行计划：

"{user_input}"

{tools_desc}

请以 JSON 对象格式响应（只返回 JSON，不要额外文字）：
```json
{{
  "goal": "用户目标（一句话总结）",
  "steps": [
    {{
      "step_id": 1,
      "description": "本步骤的具体描述（越详细越好，包含子任务）",
      "tool_name": "要使用的工具名",
      "tool_args": {{}},
      "expected_output": "预期产出"
    }}
  ],
  "needs_clarification": false,
  "clarification_question": null
}}
```

规划原则：
1. **聚焦路径**：当用户没有给出具体路径但提到项目名时，优先使用常见根目录组合（如 "C:\\Users\\<用户名>\\<项目名>"），不要生成大量"尝试多路径"的步骤
2. **控制步数**：步骤数必须 ≤ 6 步。合并同类操作，避免过度拆分
3. **参数必须详细**：路径使用绝对路径；文件名要具体；过滤 pattern 要具体
4. **中文友好**：工具参数中的字符串可以使用中文，路径必须是 Windows 绝对路径
5. **主动探索**：第一次 list_files 成功后，后续步骤基于该结果展开，不要回退到"尝试其他路径"
6. **只有在确实不需要任何工具时**（如纯问候、简单对话），才返回空的 steps 列表
7. **模糊请求**：设置 needs_clarification=true 并提出具体澄清问题
8. **步骤间数据传递（重要）**：如果后续步骤需要用到前序步骤的工具结果，参数值必须写模板引用，格式为 "{{step_N_result.字段名}}"（step_N_result 是第 N 步的输出对象，用 .字段名 提取具体字段）。例如第 1 步 query_hardware_history 返回含 timestamps/values，第 2 步画图时应写 "x_data": "{{step_1_result.timestamps}}"、"y_data": "{{step_1_result.values}}"。
9. **严格只返回 JSON**，不要加任何解释性文字或 Markdown 代码块外的内容"""

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """从 LLM 输出中尽可能稳健地抽取第一个 JSON 对象。

        支持：
        - 纯 JSON
        - ```json ... ``` 代码块
        - 前后有多余文字 / 解释
        """
        text = text.strip()

        # 1) 尝试直接解析
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # 2) 尝试提取 ``` ... ``` 块
        if "```" in text:
            in_code = False
            buf: list[str] = []
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("```"):
                    if not in_code:
                        in_code = True
                        continue
                    else:
                        if buf:
                            candidate = "\n".join(buf)
                            try:
                                json.loads(candidate)
                                return candidate
                            except json.JSONDecodeError:
                                pass
                        in_code = False
                        continue
                if in_code:
                    buf.append(line)
            if buf:
                candidate = "\n".join(buf)
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    pass

        # 3) 找第一个 '{' 到最后一个 '}'
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = text[first : last + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _parse_llm_plan(llm_output: str, user_input: str) -> Plan:
        """解析 LLM 输出的规划。"""
        json_str = Planner._extract_json_object(llm_output)

        if json_str is None:
            logger.bind(component="planner").warning(
                "Failed to extract JSON from LLM output, using simple plan"
            )
            return Plan(
                goal=user_input,
                steps=[
                    PlanStep(
                        step_id=1,
                        description=user_input,
                        tool_name=None,
                        tool_args={},
                        expected_output="LLM response",
                    )
                ],
                needs_clarification=False,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.bind(component="planner").warning(
                "Failed to parse JSON, using simple plan"
            )
            return Plan(
                goal=user_input,
                steps=[
                    PlanStep(
                        step_id=1,
                        description=user_input,
                        tool_name=None,
                        tool_args={},
                        expected_output="LLM response",
                    )
                ],
                needs_clarification=False,
            )

        steps = []
        for s in data.get("steps", []):
            steps.append(
                PlanStep(
                    step_id=s.get("step_id", len(steps) + 1),
                    description=s.get("description", ""),
                    tool_name=s.get("tool_name"),
                    tool_args=s.get("tool_args", {}),
                    expected_output=s.get("expected_output", ""),
                )
            )

        return Plan(
            goal=data.get("goal", user_input),
            steps=steps,
            needs_clarification=data.get("needs_clarification", False),
            clarification_question=data.get("clarification_question"),
        )


__all__ = [
    "PlanStep",
    "Plan",
    "Planner",
]
