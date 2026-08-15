"""
硬件遥测采集服务。

周期性读取硬件设备指标（当前为 Mock 数据源），批量写入
DeviceTelemetryHistory 表，为 query_hardware_history 工具提供历史数据。

以 asyncio 后台任务运行，不阻塞主 API 路由。
"""

from __future__ import annotations

import asyncio
import datetime
import time
from typing import Any

from loguru import logger
from sqlalchemy import delete, select

from app.core.config import settings


class HardwareCollectorService:
    """硬件遥测采集器。

    后台轮询循环，按固定间隔从设备源读取指标并写入数据库。

    Usage::

        collector = HardwareCollectorService()
        await collector.start()
        # ... 应用运行 ...
        await collector.stop()
    """

    def __init__(self, interval: float | None = None) -> None:
        self._interval = interval or settings.hardware_collect_interval
        self._retention_minutes = settings.hardware_history_retention_minutes
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_collect_time = 0.0
        logger.bind(component="hardware_collector").info(
            "HardwareCollectorService initialized (interval={}s)", self._interval
        )

    # -- 生命周期 -----------------------------------------------------------

    async def start(self) -> None:
        """启动后台采集循环。"""
        if self._running:
            logger.bind(component="hardware_collector").warning(
                "HardwareCollectorService already running"
            )
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.bind(component="hardware_collector").info(
            "HardwareCollectorService started (interval={}s)", self._interval
        )

    async def stop(self) -> None:
        """停止后台采集循环。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.bind(component="hardware_collector").info(
            "HardwareCollectorService stopped"
        )

    # -- 内部循环 -----------------------------------------------------------

    async def _run_loop(self) -> None:
        """后台轮询主循环。异常不会中断循环。"""
        while self._running:
            try:
                await self._collect_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.bind(component="hardware_collector").error(
                    "Telemetry collect iteration failed: {}", exc
                )
            await asyncio.sleep(self._interval)
        logger.bind(component="hardware_collector").debug(
            "HardwareCollectorService loop exited"
        )

    async def _collect_once(self) -> None:
        """单次采集：从统一设备源 DriverRegistry 读遥测并写入数据库。"""
        try:
            from app.services.orchestrator import get_orchestrator

            devices = await get_orchestrator()._drivers.get_device_info()
        except Exception:
            devices = []

        records = self._build_records(devices)
        if not records:
            logger.bind(component="hardware_collector").debug(
                "No telemetry records to write"
            )
            return

        from app.database.session import get_session_factory
        from app.models.tables import DeviceTelemetryHistory

        session_factory = get_session_factory()
        try:
            async with session_factory() as session:
                session.add_all(records)
                await session.commit()
            elapsed_ms = int((time.perf_counter() - self._last_collect_time) * 1000) if self._last_collect_time else 0
            self._last_collect_time = time.perf_counter()
            logger.bind(component="hardware_collector").info(
                "Telemetry collected: {} records ({:.1f}ms since last)",
                len(records), elapsed_ms,
            )
            await self._cleanup_old(session_factory)
        except Exception as exc:
            logger.bind(component="hardware_collector").error(
                "Telemetry insert failed: {}", exc
            )

    @staticmethod
    def _build_records(devices: list[dict[str, Any]]) -> list[Any]:
        """从设备数据构建 DeviceTelemetryHistory 记录。"""
        from app.models.tables import DeviceTelemetryHistory

        records = []
        for device in devices:
            device_id = device.get("id")
            for metric in device.get("metrics", []):
                try:
                    value = float(metric["value"])
                except (TypeError, ValueError, KeyError):
                    continue
                records.append(
                    DeviceTelemetryHistory(
                        device_id=device_id,
                        metric_name=str(metric["name"]),
                        metric_value=value,
                        unit=metric.get("unit"),
                    )
                )
        return records

    async def _cleanup_old(self, session_factory) -> None:
        """清理超过保留窗口的旧记录，避免表无限膨胀。"""
        from app.models.tables import DeviceTelemetryHistory

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=self._retention_minutes
        )
        try:
            async with session_factory() as session:
                result = await session.execute(
                    delete(DeviceTelemetryHistory).where(
                        DeviceTelemetryHistory.timestamp < cutoff
                    )
                )
                await session.commit()
                deleted = result.rowcount
                if deleted:
                    logger.bind(component="hardware_collector").debug(
                        "Cleaned {} stale telemetry records", deleted
                    )
        except Exception as exc:
            logger.bind(component="hardware_collector").error(
                "Telemetry cleanup failed: {}", exc
            )


# 全局单例
_collector: HardwareCollectorService | None = None


def get_hardware_collector() -> HardwareCollectorService:
    """获取全局 HardwareCollectorService 实例。"""
    global _collector
    if _collector is None:
        _collector = HardwareCollectorService()
    return _collector


__all__ = [
    "HardwareCollectorService",
    "get_hardware_collector",
]
