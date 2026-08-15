"""
硬件设备管理端点。

从统一设备源 DriverRegistry 读取设备列表、状态、遥测，下发指令。
DriverRegistry 由 orchestrator 初始化（从 hardware_simulation_data.json 加载
6 台油化仿真设备：HTHP/Rheo/Thick）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(tags=["hardware"])


class CommandRequest(BaseModel):
    command: str = Field(..., description="要下发的指令，如 start/stop/reset/calibrate")
    params: dict[str, Any] = Field(default_factory=dict, description="指令参数")


class GenericResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


def _get_registry():
    """获取全局 DriverRegistry。"""
    from app.services.orchestrator import get_orchestrator

    return get_orchestrator()._drivers


@router.get("/hardware/devices")
async def list_devices() -> dict:
    """列出所有硬件设备（统一设备源 DriverRegistry）。"""
    devices = await _get_registry().get_device_info()
    return {"devices": devices}


@router.get("/hardware/devices/{device_id}")
async def get_device(device_id: str) -> dict:
    """获取单个设备详情。"""
    devices = await _get_registry().get_device_info()
    for d in devices:
        if d["id"] == device_id:
            return {"device": d}
    raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")


@router.post("/hardware/devices/{device_id}/command")
async def send_command(device_id: str, req: CommandRequest) -> GenericResponse:
    """向设备下发指令（从统一设备源 DriverRegistry 取设备）。"""
    driver = _get_registry().get(device_id)
    if driver is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    try:
        result = await driver.send_command(req.command, req.params)
        return GenericResponse(
            success=True,
            data=result,
            message=result.get("message", "指令已下发"),
        )
    except Exception as exc:
        logger.bind(component="hardware").error("指令下发异常: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


__all__ = ["router"]
