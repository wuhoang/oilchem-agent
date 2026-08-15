"""
app.hardware.drivers — 设备驱动实现。

- base.py：DeviceDriver 抽象接口 + 关键类型（StepResult/TelemetryPoint/DeviceStatus）
- mock.py：MockDriver 剧本引擎（演示版）
- registry.py：DriverRegistry 设备占用管理
"""

from app.hardware.drivers.base import (
    DeviceDriver,
    DeviceStatus,
    StepResult,
    TelemetryPoint,
)
from app.hardware.drivers.mock import MockDriver
from app.hardware.drivers.registry import DriverRegistry

__all__ = [
    "DeviceDriver",
    "DeviceStatus",
    "StepResult",
    "TelemetryPoint",
    "MockDriver",
    "DriverRegistry",
]
