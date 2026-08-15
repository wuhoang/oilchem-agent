"""
实验域 REST API（M5）。

方案库、实验创建/启动/进度/数据查询、异常介入、看板聚合。
所有端点共享 M2 编排引擎与 M1 数据模型。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db, get_session_factory
from app.models.tables import (
    Experiment,
    ExperimentStep,
    Measurement,
    Protocol,
    ProtocolStep,
)

router = APIRouter(tags=["experiments"])


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., description="实验名称")
    protocol_id: str = Field(..., description="方案 ID")
    operator_id: str = Field(..., description="操作实验员 ID")
    sample_code: str | None = Field(default=None, description="样品编号")


class InterveneRequest(BaseModel):
    step_order: int = Field(..., description="步骤序号")


# ---------------------------------------------------------------------------
# 方案库
# ---------------------------------------------------------------------------


@router.get("/protocols")
async def list_protocols(db: AsyncSession = Depends(get_db)) -> dict:
    """列出所有实验方案。"""
    result = await db.execute(select(Protocol).order_by(Protocol.id.asc()))
    protocols = result.scalars().all()
    return {
        "protocols": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "version": p.version,
                "status": p.status,
            }
            for p in protocols
        ]
    }


@router.get("/protocols/{protocol_id}")
async def get_protocol(protocol_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """获取方案详情（含步骤模板）。"""
    proto = await db.get(Protocol, protocol_id)
    if proto is None:
        raise HTTPException(status_code=404, detail=f"方案不存在: {protocol_id}")

    result = await db.execute(
        select(ProtocolStep)
        .where(ProtocolStep.protocol_id == protocol_id)
        .order_by(ProtocolStep.step_order.asc())
    )
    steps = result.scalars().all()
    return {
        "protocol": {
            "id": proto.id,
            "name": proto.name,
            "description": proto.description,
            "version": proto.version,
            "status": proto.status,
        },
        "steps": [
            {
                "step_order": s.step_order,
                "device_id": s.device_id,
                "action": s.action,
                "params": s.params,
                "description": s.description,
            }
            for s in steps
        ],
    }


# ---------------------------------------------------------------------------
# 实验生命周期
# ---------------------------------------------------------------------------


@router.get("/experiments")
async def list_experiments(db: AsyncSession = Depends(get_db)) -> dict:
    """列出所有实验（看板用）。"""
    result = await db.execute(select(Experiment).order_by(Experiment.id.desc()))
    experiments = result.scalars().all()
    return {
        "experiments": [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "operator": e.operator,
                "protocol_id": e.protocol_id,
                "sample_code": e.sample_code,
            }
            for e in experiments
        ]
    }


@router.post("/experiments")
async def create_experiment(req: CreateExperimentRequest) -> dict:
    """创建实验。"""
    from app.services.orchestrator import get_orchestrator

    orch = get_orchestrator()
    try:
        result = await orch.create_experiment(
            name=req.name,
            protocol_id=req.protocol_id,
            operator_id=req.operator_id,
            sample_code=req.sample_code,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: str) -> dict:
    """启动实验。"""
    from app.services.orchestrator import get_orchestrator

    orch = get_orchestrator()
    try:
        await orch.start(experiment_id)
        return {"success": True, "message": f"实验 {experiment_id} 已启动"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/experiments/{experiment_id}/retry-step")
async def retry_step(experiment_id: str, req: InterveneRequest) -> dict:
    """重试失败步骤。"""
    from app.services.orchestrator import get_orchestrator

    orch = get_orchestrator()
    await orch.retry_step(experiment_id, req.step_order)
    return {"success": True, "message": f"步骤 {req.step_order} 已重试"}


@router.post("/experiments/{experiment_id}/skip-step")
async def skip_step(experiment_id: str, req: InterveneRequest) -> dict:
    """跳过失败步骤。"""
    from app.services.orchestrator import get_orchestrator

    orch = get_orchestrator()
    await orch.skip_step(experiment_id, req.step_order)
    return {"success": True, "message": f"步骤 {req.step_order} 已跳过"}


@router.post("/experiments/{experiment_id}/abort")
async def abort_experiment(experiment_id: str) -> dict:
    """中止实验。"""
    from app.services.orchestrator import get_orchestrator

    orch = get_orchestrator()
    await orch.abort(experiment_id)
    return {"success": True, "message": f"实验 {experiment_id} 已中止"}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """获取实验详情（含步骤 + 追溯链）。"""
    exp = await db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"实验不存在: {experiment_id}")

    result = await db.execute(
        select(ExperimentStep)
        .where(ExperimentStep.experiment_id == experiment_id)
        .order_by(ExperimentStep.step_order.asc())
    )
    steps = result.scalars().all()

    return {
        "experiment": {
            "id": exp.id,
            "name": exp.name,
            "status": exp.status,
            "operator": exp.operator,
            "operator_id": exp.operator_id,
            "protocol_id": exp.protocol_id,
            "sample_code": exp.sample_code,
            "created_at": exp.created_at,
            "result": exp.result,
        },
        "steps": [
            {
                "step_order": s.step_order,
                "device_id": s.device_id,
                "action": s.action,
                "status": s.status,
                "error": s.error_message,
            }
            for s in steps
        ],
    }


@router.get("/experiments/{experiment_id}/progress")
async def get_progress(experiment_id: str) -> dict:
    """获取实验进度快照。"""
    from app.services.orchestrator import get_orchestrator

    orch = get_orchestrator()
    try:
        return await orch.get_progress(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/experiments/{experiment_id}/measurements")
async def get_measurements(
    experiment_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """获取实验测量数据（时间序列，供曲线绘制）。"""
    result = await db.execute(
        select(Measurement)
        .where(Measurement.experiment_id == experiment_id)
        .order_by(Measurement.timestamp.asc())
    )
    measurements = result.scalars().all()
    return {
        "measurements": [
            {
                "metric_name": m.metric_name,
                "value": m.metric_value,
                "unit": m.unit,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in measurements
        ]
    }


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)) -> dict:
    """看板聚合：设备/实验进度/统计。"""
    result = await db.execute(select(Experiment))
    experiments = result.scalars().all()
    status_count: dict[str, int] = {}
    for e in experiments:
        status_count[e.status] = status_count.get(e.status, 0) + 1

    return {
        "total_experiments": len(experiments),
        "status_count": status_count,
        "running": [
            e.id for e in experiments if e.status in ("执行中", "待执行")
        ],
    }


__all__ = ["router"]
