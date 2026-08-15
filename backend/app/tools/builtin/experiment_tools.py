"""
实验域 Agent 工具（M5）。

让"安排做一次实验""查进度""查结果"成为自然语言入口。
复用现有 function calling 循环，内部调用 M2 编排引擎。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.tools.base import BaseTool, ToolMetadata, ToolResult
from app.tools.registry import register_tool


@register_tool(ToolMetadata(
    name="list_protocols",
    description="列出所有可用的实验方案（protocols）。当用户想了解有哪些实验可以做、"
    "或想选择一个方案来运行时使用。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
))
class ListProtocolsTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        from app.database.session import get_session_factory
        from app.models.tables import Protocol

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(Protocol))
            protocols = result.scalars().all()
        return ToolResult(
            success=True,
            data=[
                {"id": p.id, "name": p.name, "description": p.description}
                for p in protocols
            ],
        )


@register_tool(ToolMetadata(
    name="create_experiment",
    description="创建一个实验。需提供方案ID（protocol_id）和操作员ID（operator_id），"
    "可选样品编号（sample_code）。创建后需再调用 start_experiment 才能开始执行。",
    parameters={
        "type": "object",
        "properties": {
            "protocol_id": {"type": "string", "description": "方案ID，如 PROTO-001"},
            "operator_id": {"type": "string", "description": "操作员ID，如 OP-001"},
            "sample_code": {"type": "string", "description": "样品编号（可选），如 S-2026-0801"},
        },
        "required": ["protocol_id", "operator_id"],
    },
))
class CreateExperimentTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        protocol_id = kwargs.get("protocol_id", "").strip()
        operator_id = kwargs.get("operator_id", "").strip()
        sample_code = kwargs.get("sample_code") or None

        if not protocol_id or not operator_id:
            return ToolResult(success=False, error="缺少 protocol_id 或 operator_id")

        from app.services.orchestrator import get_orchestrator

        orch = get_orchestrator()
        try:
            exp = await orch.create_experiment(
                name=f"实验 {protocol_id}",
                protocol_id=protocol_id,
                operator_id=operator_id,
                sample_code=sample_code,
            )
            return ToolResult(success=True, data=exp)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))


@register_tool(ToolMetadata(
    name="start_experiment",
    description="启动一个已创建但未运行的实验。启动后系统自动拆解步骤并驱动设备执行。",
    parameters={
        "type": "object",
        "properties": {
            "experiment_id": {"type": "string", "description": "实验ID，如 EXP-ABC123"},
        },
        "required": ["experiment_id"],
    },
))
class StartExperimentTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        experiment_id = kwargs.get("experiment_id", "").strip()
        if not experiment_id:
            return ToolResult(success=False, error="缺少 experiment_id")

        from app.services.orchestrator import get_orchestrator

        orch = get_orchestrator()
        try:
            await orch.start(experiment_id)
            return ToolResult(success=True, data={"experiment_id": experiment_id, "started": True})
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))


@register_tool(ToolMetadata(
    name="query_experiment_progress",
    description="查询实验的当前进度：状态、各步骤执行情况。当用户问'实验进行到哪了'时使用。",
    parameters={
        "type": "object",
        "properties": {
            "experiment_id": {"type": "string", "description": "实验ID"},
        },
        "required": ["experiment_id"],
    },
))
class QueryExperimentProgressTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        experiment_id = kwargs.get("experiment_id", "").strip()
        if not experiment_id:
            return ToolResult(success=False, error="缺少 experiment_id")

        from app.services.orchestrator import get_orchestrator

        orch = get_orchestrator()
        try:
            progress = await orch.get_progress(experiment_id)
            return ToolResult(success=True, data=progress)
        except KeyError as exc:
            return ToolResult(success=False, error=str(exc))


@register_tool(ToolMetadata(
    name="query_experiment_result",
    description="查询实验的测量结果数据（时间序列）。当用户问'实验结果如何''数据是什么'时使用。",
    parameters={
        "type": "object",
        "properties": {
            "experiment_id": {"type": "string", "description": "实验ID"},
        },
        "required": ["experiment_id"],
    },
))
class QueryExperimentResultTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        experiment_id = kwargs.get("experiment_id", "").strip()
        if not experiment_id:
            return ToolResult(success=False, error="缺少 experiment_id")

        from app.database.session import get_session_factory
        from app.models.tables import Measurement

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Measurement)
                .where(Measurement.experiment_id == experiment_id)
                .order_by(Measurement.timestamp.asc())
            )
            measurements = result.scalars().all()

        if not measurements:
            return ToolResult(success=False, error=f"实验 {experiment_id} 暂无测量数据")

        return ToolResult(
            success=True,
            data={
                "experiment_id": experiment_id,
                "count": len(measurements),
                "measurements": [
                    {
                        "metric_name": m.metric_name,
                        "value": m.metric_value,
                        "unit": m.unit,
                    }
                    for m in measurements
                ],
            },
        )


@register_tool(ToolMetadata(
    name="generate_experiment_report",
    description="为指定实验生成报告文件（Word + Excel）。一次调用即可完成："
    "查询实验数据、生成 Word 报告（含信息表/步骤/数据/审计）和 Excel 数据表，"
    "返回文件路径。当用户要求'生成实验报告''导出报告'时使用此工具。",
    parameters={
        "type": "object",
        "properties": {
            "experiment_id": {"type": "string", "description": "实验ID，如 EXP-ABC123"},
        },
        "required": ["experiment_id"],
    },
))
class GenerateExperimentReportTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        experiment_id = kwargs.get("experiment_id", "").strip()
        if not experiment_id:
            return ToolResult(success=False, error="缺少 experiment_id")

        from app.services.report_generator import generate_report

        try:
            result = await generate_report(experiment_id)
            return ToolResult(
                success=True,
                data={
                    "experiment_id": experiment_id,
                    "word_path": result["word_path"],
                    "excel_path": result["excel_path"],
                    "message": f"报告已生成：Word={result['word_path']}，Excel={result['excel_path']}",
                },
            )
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = [
    "ListProtocolsTool",
    "CreateExperimentTool",
    "StartExperimentTool",
    "QueryExperimentProgressTool",
    "QueryExperimentResultTool",
    "GenerateExperimentReportTool",
]
