"""
DriverRegistry — 设备驱动注册表（M3）。

管理设备驱动实例的创建、占用、释放。设备同时只服务一个实验，
冲突时抛 BusyError。
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.hardware.drivers.base import DeviceDriver


class BusyError(Exception):
    """设备已被占用。"""


class DriverRegistry:
    """设备驱动注册表。

    Usage::

        registry = DriverRegistry()
        registry.register("rct-01", MockDriver("rct-01", ...))
        driver = await registry.acquire("rct-01", "EXP-001")
        ...
        await registry.release("rct-01")
    """

    def __init__(self) -> None:
        self._drivers: dict[str, DeviceDriver] = {}
        self._owner: dict[str, str | None] = {}  # device_id -> experiment_id
        self._lock = asyncio.Lock()

    def register(self, device_id: str, driver: DeviceDriver) -> None:
        self._drivers[device_id] = driver
        self._owner[device_id] = None

    def get(self, device_id: str) -> DeviceDriver | None:
        return self._drivers.get(device_id)

    async def acquire(self, device_id: str, experiment_id: str) -> DeviceDriver:
        """占用设备；冲突抛 BusyError。"""
        async with self._lock:
            if device_id not in self._drivers:
                raise KeyError(f"设备未注册: {device_id}")
            owner = self._owner.get(device_id)
            if owner is not None and owner != experiment_id:
                raise BusyError(f"设备 {device_id} 已被实验 {owner} 占用")
            self._owner[device_id] = experiment_id
            logger.bind(component="driver_registry").info(
                "设备占用: device={}, experiment={}", device_id, experiment_id
            )
            return self._drivers[device_id]

    async def release(self, device_id: str) -> None:
        async with self._lock:
            if device_id in self._owner:
                self._owner[device_id] = None
                logger.bind(component="driver_registry").info(
                    "设备释放: device={}", device_id
                )

    def list_devices(self) -> list[str]:
        return list(self._drivers.keys())

    async def get_device_info(self) -> list[dict[str, Any]]:
        """返回所有设备的统一 dict 格式（含遥测与状态），供硬件 API 使用。"""
        infos = []
        for device_id, driver in self._drivers.items():
            try:
                status = await driver.get_status()
                telemetry = await driver.read_telemetry()
                infos.append(
                    {
                        "id": device_id,
                        "name": getattr(driver, "name", device_id),
                        "type": getattr(driver, "type", "device"),
                        "status": "online" if status.value != "offline" else "offline",
                        "metrics": [
                            {
                                "name": tp.metric_name,
                                "value": tp.value,
                                "unit": tp.unit or "",
                            }
                            for tp in telemetry
                        ],
                    }
                )
            except Exception as exc:
                infos.append(
                    {"id": device_id, "name": device_id, "type": "device", "status": "error", "metrics": [], "error": str(exc)}
                )
        return infos


__all__ = ["DriverRegistry", "BusyError"]
