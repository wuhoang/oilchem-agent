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
    category="experiment",
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
    name="list_experiments",
    category="experiment",
    description="列出最近的实验记录（按创建时间倒序）。当用户问'最近的实验''有哪些实验'或"
    "需要先查实验ID再查结果时，优先使用此工具。返回实验ID、名称、状态、操作员。",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "返回条数，默认 10", "default": 10},
            "status": {"type": "string", "description": "按状态过滤（可选），如 已完成、待审核、执行中"},
        },
        "required": [],
    },
))
class ListExperimentsTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        from app.database.session import get_session_factory
        from app.models.tables import Experiment

        limit = kwargs.get("limit", 10)
        status_filter = kwargs.get("status")

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Experiment).order_by(Experiment.created_at.desc())
            if status_filter:
                stmt = stmt.where(Experiment.status == status_filter)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            experiments = result.scalars().all()

        return ToolResult(
            success=True,
            data=[
                {
                    "id": e.id,
                    "name": e.name,
                    "status": e.status,
                    "operator": e.operator,
                    "created_at": str(e.created_at) if e.created_at else None,
                }
                for e in experiments
            ],
        )


@register_tool(ToolMetadata(
    name="create_experiment",
    category="experiment",
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
    category="experiment",
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
    category="experiment",
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
    category="experiment",
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

        from app.services.orchestrator import get_orchestrator

        measurements = await get_orchestrator().get_measurements(experiment_id)

        if not measurements:
            return ToolResult(success=False, error=f"实验 {experiment_id} 暂无测量数据")

        return ToolResult(
            success=True,
            data={
                "experiment_id": experiment_id,
                "count": len(measurements),
                "measurements": measurements,
            },
        )


@register_tool(ToolMetadata(
    name="generate_experiment_report",
    category="experiment",
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


# ---------------------------------------------------------------------------
# 资源查询工具（设备台账、样品、人员）
# ---------------------------------------------------------------------------


@register_tool(ToolMetadata(
    name="list_devices",
    category="hardware",
    description="查询设备台账信息（设备ID、名称、型号、状态、上次维护时间）。"
    "当用户问'有哪些设备''设备型号''设备台账'时使用。"
    "注意：这是数据库里的静态信息，不同于 read_hardware（实时遥测数据）。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
))
class ListDevicesTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        from app.database.session import get_session_factory
        from app.models.tables import Device

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(Device))
            devices = result.scalars().all()

        return ToolResult(
            success=True,
            data=[
                {
                    "id": d.id,
                    "name": d.name,
                    "model": d.model,
                    "status": d.status,
                    "last_maintain": str(d.last_maintain) if d.last_maintain else None,
                }
                for d in devices
            ],
        )


@register_tool(ToolMetadata(
    name="list_samples",
    category="experiment",
    description="查询样品信息（样品号、名称、批次、存放位置、状态）。"
    "当用户问'有哪些样品''样品在哪''样品台账'时使用。",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "返回条数，默认 20", "default": 20},
        },
        "required": [],
    },
))
class ListSamplesTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        from app.database.session import get_session_factory
        from app.models.tables import Sample

        limit = kwargs.get("limit", 20)
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Sample).order_by(Sample.code).limit(limit)
            )
            samples = result.scalars().all()

        return ToolResult(
            success=True,
            data=[
                {
                    "code": s.code,
                    "name": s.name,
                    "batch": s.batch,
                    "location": s.location,
                    "status": s.status,
                }
                for s in samples
            ],
        )


@register_tool(ToolMetadata(
    name="list_personnel",
    category="experiment",
    description="查询实验人员信息（工号、姓名、角色）。"
    "当用户问'有哪些人''实验员''审核人''人员列表'时使用。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
))
class ListPersonnelTool(BaseTool):
    async def execute(self, **kwargs: Any) -> ToolResult:
        from app.database.session import get_session_factory
        from app.models.tables import Experimenter

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(Experimenter))
            personnel = result.scalars().all()

        return ToolResult(
            success=True,
            data=[
                {
                    "id": p.id,
                    "name": p.name,
                    "role": p.role,
                }
                for p in personnel
            ],
        )


__all__ = [
    "ListExperimentsTool",
    "ListProtocolsTool",
    "ListDevicesTool",
    "ListSamplesTool",
    "ListPersonnelTool",
    "CreateExperimentTool",
    "StartExperimentTool",
    "QueryExperimentProgressTool",
    "QueryExperimentResultTool",
    "GenerateExperimentReportTool",
]
