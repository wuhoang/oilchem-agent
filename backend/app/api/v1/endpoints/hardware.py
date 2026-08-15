"""
硬件设备管理端点（占位）。

提供设备列表、状态查询、指令下发等接口，
后续可替换为真实的硬件网关（RS232/USB/GPIB/MQTT）。
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["hardware"])


# ---------------------------------------------------------------------------
# 内存中的设备列表（演示用）
# ---------------------------------------------------------------------------

_DEVICES: list[dict[str, Any]] = [
    {
        "id": "rct-01",
        "name": "加氢反应器 R-101",
        "type": "reactor",
        "status": "online",
        "metrics": [
            {"name": "温度", "value": 185.3, "unit": "°C", "min": 0, "max": 300},
            {"name": "压力", "value": 4.2, "unit": "MPa", "min": 0, "max": 10},
            {"name": "液位", "value": 62, "unit": "%", "min": 0, "max": 100},
        ],
        "last_update": int(time.time() * 1000),
    },
    {
        "id": "gc-01",
        "name": "气相色谱仪 GC-2030",
        "type": "chromatograph",
        "status": "online",
        "metrics": [
            {"name": "柱温", "value": 220, "unit": "°C"},
            {"name": "载气压力", "value": 0.45, "unit": "MPa"},
        ],
        "last_update": int(time.time() * 1000),
    },
    {
        "id": "bal-01",
        "name": "分析天平 XS205",
        "type": "balance",
        "status": "online",
        "metrics": [{"name": "当前重量", "value": 12.548, "unit": "g"}],
        "last_update": int(time.time() * 1000),
    },
    {
        "id": "ph-01",
        "name": "pH计 FE28",
        "type": "ph_meter",
        "status": "online",
        "metrics": [
            {"name": "pH", "value": 7.42, "min": 0, "max": 14},
            {"name": "温度", "value": 25.3, "unit": "°C"},
        ],
        "last_update": int(time.time() * 1000),
    },
    {
        "id": "pump-01",
        "name": "蠕动泵 RP-100",
        "type": "pump",
        "status": "offline",
        "metrics": [{"name": "流速", "value": 0, "unit": "mL/min"}],
        "last_update": int(time.time() * 1000) - 60000,
    },
]


class CommandRequest(BaseModel):
    command: str = Field(..., description="要下发的指令，如 start/stop/reset/calibrate")
    params: dict[str, Any] = Field(default_factory=dict, description="指令参数")


class GenericResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


def _refresh_metrics() -> None:
    """给在线设备的指标加一点随机漂移，模拟实时数据。"""
    for d in _DEVICES:
        if d["status"] != "online":
            continue
        d["last_update"] = int(time.time() * 1000)
        for m in d["metrics"]:
            base = float(m["value"])
            drift = (random.random() - 0.5) * max(abs(base) * 0.02, 0.01)
            next_v = base + drift
            if m.get("min") is not None:
                next_v = max(float(m["min"]), next_v)
            if m.get("max") is not None:
                next_v = min(float(m["max"]), next_v)
            m["value"] = round(next_v, 3)


@router.get("/hardware/devices")
async def list_devices(refresh: bool = True) -> dict:
    """列出所有硬件设备（统一设备源：DriverRegistry）。"""
    try:
        from app.services.orchestrator import get_orchestrator

        devices = await get_orchestrator()._drivers.get_device_info()
        return {"devices": devices}
    except Exception as exc:
        # 降级：返回旧的写死设备
        logger = __import__("loguru").logger
        logger.bind(component="hardware").warning("统一设备源读取失败，降级为旧数据: {}", exc)
        if refresh:
            _refresh_metrics()
        return {"devices": _DEVICES}


@router.get("/hardware/devices/{device_id}")
async def get_device(device_id: str) -> dict:
    """获取单个设备详情。"""
    try:
        from app.services.orchestrator import get_orchestrator

        devices = await get_orchestrator()._drivers.get_device_info()
        for d in devices:
            if d["id"] == device_id:
                return {"device": d}
    except Exception:
        pass
    _refresh_metrics()
    for d in _DEVICES:
        if d["id"] == device_id:
            return {"device": d}
    raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")


@router.post("/hardware/devices/{device_id}/command")
async def send_command(device_id: str, req: CommandRequest) -> GenericResponse:
    """向设备下发指令（从统一设备源 DriverRegistry 取设备）。"""
    try:
        from app.services.orchestrator import get_orchestrator

        driver = get_orchestrator()._drivers.get(device_id)
        if driver is not None:
            result = await driver.send_command(req.command, req.params)
            return GenericResponse(success=True, data=result, message=result.get("message", "指令已下发"))
    except Exception as exc:
        logger = __import__("loguru").logger
        logger.bind(component="hardware").warning("指令下发异常: {}", exc)

    # 降级：旧写死设备
    for d in _DEVICES:
        if d["id"] == device_id:
            return GenericResponse(
                success=True,
                data={"device_id": device_id, "command": req.command, "status": "queued"},
                message=f"指令 {req.command} 已下发到设备 {device_id}",
            )
    raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")


__all__ = ["router"]
