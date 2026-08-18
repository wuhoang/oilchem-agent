"""
MockDriver — 演示版设备驱动（M3）。

受编排引擎指挥的设备模拟器：
- set_temperature / ramp：按爬坡速率逐步逼近目标温度
- hold：计时保持当前值
- measure：按剧本曲线产出测量数据点
- 每个 tick 更新内部遥测，供 read_telemetry 拉取

设备行为参数从行为库（device behaviors）实例化。
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

from loguru import logger

from app.hardware.drivers.base import (
    DeviceDriver,
    DeviceStatus,
    StepResult,
    TelemetryPoint,
)


class MockDriver(DeviceDriver):
    """剧本化模拟设备。

    Parameters
    ----------
    device_id:
        设备 ID（对应 devices.id）。
    metrics:
        设备指标定义，如 [{"name": "温度", "unit": "°C", "initial": 25}]
    tick_s:
        内部 tick 间隔（秒），决定数据曲线的粒度。演示版可用较小值。
    """

    def __init__(
        self,
        device_id: str,
        metrics: list[dict[str, Any]] | None = None,
        tick_s: float = 0.5,
        curve: dict[str, list[float]] | None = None,
        name: str = "",
        type_: str = "device",
    ) -> None:
        self.device_id = device_id
        self.name = name or device_id
        self.type = type_
        self._tick_s = tick_s
        self._metrics: dict[str, dict[str, Any]] = {}
        self._initial_metrics: dict[str, float] = {}
        for m in metrics or []:
            name = m["name"]
            initial = float(m.get("initial", 0))
            self._metrics[name] = {
                "value": initial,
                "unit": m.get("unit"),
            }
            self._initial_metrics[name] = initial
        # 剧本曲线：metric_name -> 值序列（measure 时按序产出）
        self._curve = curve or {}
        self._curve_index: dict[str, int] = {}
        self._status = DeviceStatus.IDLE
        self._cancel_requested = False
        logger.bind(component="mock_driver").info(
            "MockDriver initialized: device={}, metrics={}",
            device_id, list(self._metrics.keys()),
        )

    # -- 生命周期 -----------------------------------------------------------

    async def connect(self) -> None:
        self._status = DeviceStatus.IDLE

    async def disconnect(self) -> None:
        self._status = DeviceStatus.OFFLINE

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def cancel(self) -> None:
        self._cancel_requested = True

    async def reset(self) -> None:
        """复位设备：指标回初始值、曲线索引清零、状态回 IDLE。"""
        for name, initial in self._initial_metrics.items():
            if name in self._metrics:
                self._metrics[name]["value"] = initial
        self._curve_index.clear()
        self._cancel_requested = False
        self._status = DeviceStatus.IDLE
        logger.bind(component="mock_driver").debug(
            "设备复位: device={}", self.device_id
        )

    # -- 遥测 ---------------------------------------------------------------

    async def read_telemetry(self) -> list[TelemetryPoint]:
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        return [
            TelemetryPoint(
                metric_name=name,
                value=float(meta["value"]),
                unit=meta.get("unit"),
                timestamp=now,
            )
            for name, meta in self._metrics.items()
        ]

    def advance_curve(self, metric_name: str) -> None:
        """推进剧本曲线到下一个值（供采集循环调用）。"""
        if metric_name in self._curve:
            idx = self._curve_index.get(metric_name, 0)
            if idx < len(self._curve[metric_name]):
                self._metrics[metric_name]["value"] = self._curve[metric_name][idx]
                self._curve_index[metric_name] = idx + 1

    async def send_command(self, command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """通用指令下发（模拟响应 + 日志）。"""
        logger.bind(component="mock_driver").info(
            "下发指令: device={}, command={}, params={}",
            self.device_id, command, params or {},
        )
        return {
            "device_id": self.device_id,
            "command": command,
            "status": "queued",
            "message": f"指令 {command} 已下发到 {self.device_id}（模拟）",
        }

    async def execute_step(self, step: dict[str, Any]) -> StepResult:
        """执行一步。根据 action 分派到对应剧本。"""
        self._cancel_requested = False
        self._status = DeviceStatus.BUSY

        action = step.get("action", "")
        params = step.get("params", {})
        try:
            if action == "set_temperature":
                return await self._set_temperature(params)
            elif action == "ramp":
                return await self._ramp(params)
            elif action == "hold":
                return await self._hold(params)
            elif action == "measure":
                return await self._measure(params, step)
            elif action == "load_sample":
                return StepResult(success=True, message="装样完成")
            elif action == "drain":
                return StepResult(success=True, message="排空完成")
            elif action == "report":
                return StepResult(success=True, message="报告已生成")
            else:
                return StepResult(
                    success=False,
                    status_code="unknown_action",
                    message=f"未知动作: {action}",
                )
        finally:
            if self._status != DeviceStatus.ERROR:
                self._status = DeviceStatus.IDLE

    # -- 剧本动作 -----------------------------------------------------------

    async def _set_temperature(self, params: dict[str, Any]) -> StepResult:
        """升温到目标温度（按爬坡速率逐步逼近）。"""
        target = float(params.get("target", 0))
        ramp_rate = float(params.get("ramp_rate", 1))
        current = self._metrics.get("温度", {}).get("value", 0.0)

        while abs(current - target) > 0.5:
            if self._cancel_requested:
                return StepResult(success=False, status_code="cancelled", message="升温被取消")
            step = ramp_rate * self._tick_s
            current = current + step if current < target else current - step
            current = max(target, current) if target > current else min(target, current)
            self._set_metric("温度", current)
            await asyncio.sleep(self._tick_s)

        self._set_metric("温度", float(target))
        return StepResult(success=True, message=f"已升温至 {target}°C")

    async def _ramp(self, params: dict[str, Any]) -> StepResult:
        """按速率变化到目标值（通用，作用到指定指标）。"""
        metric = params.get("metric", "温度")
        target = float(params.get("target", 0))
        rate = float(params.get("rate", 1))
        current = self._metrics.get(metric, {}).get("value", 0.0)

        while abs(current - target) > 0.5:
            if self._cancel_requested:
                return StepResult(success=False, status_code="cancelled", message="变化被取消")
            delta = rate * self._tick_s
            current = current + delta if current < target else current - delta
            current = max(target, current) if target > current else min(target, current)
            self._set_metric(metric, current)
            await asyncio.sleep(self._tick_s)

        self._set_metric(metric, float(target))
        return StepResult(success=True, message=f"{metric} 已达 {target}")

    async def _hold(self, params: dict[str, Any]) -> StepResult:
        """恒温/恒压保持指定时长。"""
        duration = float(params.get("duration_s", 60))
        elapsed = 0.0
        while elapsed < duration:
            if self._cancel_requested:
                return StepResult(success=False, status_code="cancelled", message="保持被取消")
            await asyncio.sleep(self._tick_s)
            elapsed += self._tick_s
        return StepResult(success=True, message=f"已保持 {duration}s")

    async def _measure(self, params: dict[str, Any], step: dict[str, Any]) -> StepResult:
        """采一个测量点，返回数值供引擎落库。

        若 step 带 data_points（剧本曲线），按索引依次返回；
        否则在现有指标基础上加轻微噪声。
        """
        metric_name = params.get("metric_name", "值")
        # 支持剧本曲线（HTHP 漏失量曲线）
        data_points = step.get("data_points")
        if data_points:
            idx = step.get("_measure_index", 0)
            if idx < len(data_points):
                value = float(data_points[idx])
                step["_measure_index"] = idx + 1
                self._set_metric(metric_name, value)
                return StepResult(success=True, message=str(value))

        # 无剧本：当前指标值 + 噪声
        base = self._metrics.get(metric_name, {}).get("value", 0.0)
        value = round(base + (base * 0.005 if base else 0.01), 3)
        self._set_metric(metric_name, value)
        return StepResult(success=True, message=str(value))

    # -- 内部 ---------------------------------------------------------------

    def _set_metric(self, name: str, value: float) -> None:
        if name not in self._metrics:
            self._metrics[name] = {"value": value, "unit": None}
        else:
            self._metrics[name]["value"] = value


__all__ = ["MockDriver"]
