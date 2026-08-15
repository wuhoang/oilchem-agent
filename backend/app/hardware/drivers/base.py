"""
设备驱动抽象接口（M3）。

定义编排引擎与设备驱动之间的统一契约。驱动层不感知实验语义，
只理解「动作 + 参数 + 完成判据」。
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceStatus(str, Enum):
    """设备状态。"""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class StepResult(BaseModel):
    """单步执行结果。"""

    success: bool = Field(..., description="是否成功")
    status_code: str | None = Field(default=None, description="失败错误码")
    message: str = Field(default="", description="结果描述")


class TelemetryPoint(BaseModel):
    """遥测数据点。"""

    metric_name: str = Field(..., description="指标名")
    value: float = Field(..., description="数值")
    unit: str | None = Field(default=None, description="单位")
    timestamp: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow, description="采集时间"
    )


class DeviceDriver(ABC):
    """设备驱动抽象基类。

    实现约定：
    - execute_step 是同步阻塞式：执行完成后才返回，引擎据此推进状态机。
    - read_telemetry 与执行解耦，采集线程独立轮询。
    - 异常以 StepResult 返回值表达，不抛未捕获异常。
    """

    device_id: str

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def execute_step(self, step: dict[str, Any]) -> StepResult:
        """执行一步。step 含 action/params/complete_criteria/timeout_s。"""

    @abstractmethod
    async def read_telemetry(self) -> list[TelemetryPoint]: ...

    @abstractmethod
    async def get_status(self) -> DeviceStatus: ...

    @abstractmethod
    async def cancel(self) -> None: ...

    @abstractmethod
    async def send_command(self, command: str, params: dict | None = None) -> dict:
        """下发控制指令，返回结果 dict（含 device_id/command/status/message）。"""

    @abstractmethod
    async def reset(self) -> None:
        """复位设备到初始状态（指标回初始值、曲线索引清零、状态回 IDLE）。"""


__all__ = [
    "DeviceDriver",
    "DeviceStatus",
    "StepResult",
    "TelemetryPoint",
]
