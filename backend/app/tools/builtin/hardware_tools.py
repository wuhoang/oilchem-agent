"""
硬件设备工具。

提供查询实验室硬件设备数据的工具，让 Agent 能读取
当前硬件面板显示的传感器实时数据，以及历史趋势数据。
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from app.tools.base import BaseTool, ToolMetadata, ToolResult
from app.tools.registry import register_tool


def _get_devices() -> list[dict[str, Any]]:
    """获取当前所有硬件设备数据（与 hardware.py 中的数据源共享）。"""
    from app.api.v1.endpoints.hardware import _DEVICES, _refresh_metrics

    _refresh_metrics()
    return [dict(d) for d in _DEVICES]


MAX_POINTS = 100


def _parse_start_time(value: Any) -> datetime.datetime:
    """解析开始时间参数。

    支持两种格式：
      - 纯数字（字符串）：表示相对当前时间往前 N 分钟
      - ISO 时间字符串：如 '2026-08-10T15:00:00'
    缺省为 60 分钟前。
    """
    now = datetime.datetime.utcnow()
    if value is None or value == "":
        return now - datetime.timedelta(minutes=60)

    text = str(value).strip()
    if text.isdigit():
        return now - datetime.timedelta(minutes=int(text))

    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        # 统一转为 naive UTC 以便与数据库比较
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        raise ValueError(
            f"无法解析 start_time: '{value}'。支持相对分钟数（如 '60'）或 ISO 时间（如 '2026-08-10T15:00:00'）"
        )


def _parse_end_time(value: Any) -> datetime.datetime:
    """解析结束时间参数，缺省为当前时间。"""
    if value is None or value == "":
        return datetime.datetime.utcnow()
    return _parse_start_time(value)


def _downsample(
    timestamps: list[str], values: list[float], max_points: int = MAX_POINTS
) -> tuple[list[str], list[float]]:
    """降采样：超过 max_points 个点时均匀抽取，避免上下文溢出。"""
    n = len(timestamps)
    if n <= max_points:
        return timestamps, values
    step = n / max_points
    idx = [int(i * step) for i in range(max_points)]
    return [timestamps[i] for i in idx], [values[i] for i in idx]


@register_tool(ToolMetadata(
    name="read_hardware",
    description=(
        "读取实验室硬件设备的【实时】数据快照。返回设备当前最新的传感器读数"
        "（温度、压力、液位、pH、流速等）。适用于：用户问'现在温度多少'、"
        "'某设备当前状态'、'实时读数'这类单点查询。"
        "注意：查询历史趋势/过去时间段的数值请用 query_hardware_history，"
        "不要用本工具。"
    ),
    parameters={
        "device_id": {
            "type": "string",
            "description": "设备ID（可选）。留空则返回所有设备信息。可选：rct-01(加氢反应器)、gc-01(气相色谱仪)、bal-01(分析天平)、ph-01(pH计)、pump-01(蠕动泵)",
        },
    },
))
class ReadHardwareTool(BaseTool):
    """读取硬件设备数据。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        device_id = kwargs.get("device_id", "").strip()
        try:
            devices = _get_devices()

            if device_id:
                for d in devices:
                    if d["id"] == device_id:
                        return ToolResult(
                            success=True,
                            data={
                                "device_id": d["id"],
                                "name": d["name"],
                                "type": d["type"],
                                "status": d["status"],
                                "metrics": d["metrics"],
                                "last_update": d["last_update"],
                            },
                        )
                return ToolResult(
                    success=False,
                    error=f"未找到设备 ID: {device_id}。可用设备: {[d['id'] for d in devices]}",
                )
            else:
                summary = []
                for d in devices:
                    metrics_str = ", ".join(
                        f"{m['name']}={m['value']}{m.get('unit', '')}"
                        for m in d["metrics"]
                    )
                    summary.append(
                        f"[{d['id']}] {d['name']} ({d['type']}) - {d['status']}: {metrics_str}"
                    )
                return ToolResult(
                    success=True,
                    data={
                        "total_devices": len(devices),
                        "devices": [
                            {
                                "id": d["id"],
                                "name": d["name"],
                                "type": d["type"],
                                "status": d["status"],
                                "metrics": d["metrics"],
                            }
                            for d in devices
                        ],
                        "summary": summary,
                    },
                )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


@register_tool(ToolMetadata(
    name="send_hardware_command",
    description=(
        "向实验室硬件设备下发控制指令。支持的指令：start（启动）、stop（停止）、"
        "reset（复位）、calibrate（校准）、read_params（读取参数）。"
        "当用户要求启动/停止设备或设置参数时使用此工具。"
    ),
    parameters={
        "device_id": {
            "type": "string",
            "description": "目标设备ID，如 rct-01",
        },
        "command": {
            "type": "string",
            "description": "指令名称：start / stop / reset / calibrate / read_params",
        },
        "params": {
            "type": "object",
            "description": "指令的附加参数（可选）",
        },
    },
))
class SendHardwareCommandTool(BaseTool):
    """向硬件设备下发指令。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        device_id = kwargs.get("device_id", "").strip()
        command = kwargs.get("command", "").strip()
        params = kwargs.get("params", {})

        if not device_id:
            return ToolResult(success=False, error="缺少 device_id 参数")
        if not command:
            return ToolResult(success=False, error="缺少 command 参数")

        try:
            import requests

            resp = requests.post(
                f"http://127.0.0.1:8000/api/v1/hardware/devices/{device_id}/command",
                json={"command": command, "params": params or {}},
                timeout=5,
            )
            data = resp.json()
            if resp.status_code == 200:
                return ToolResult(success=True, data=data)
            else:
                return ToolResult(
                    success=False,
                    error=f"HTTP {resp.status_code}: {data.get('detail', str(data))}",
                )
        except Exception as exc:
            return ToolResult(success=False, error=f"下发指令失败: {exc}")


@register_tool(ToolMetadata(
    name="query_hardware_history",
    description=(
        "查询硬件设备在【过去一段时间】的历史遥测数据，返回按时间排序的指标时间序列"
        "（timestamps + values）。适用于：用户问'过去X分钟/小时的变化'、'温度趋势'、"
        "'历史数据'、'画趋势图'这类时间序列查询。"
        "注意：查询当前实时读数请用 read_hardware，不要用本工具。"
        "查询结果可直接传给 plot_chart 画趋势图（x 用 timestamps，y 用 values）。"
    ),
    parameters={
        "device_id": {
            "type": "string",
            "description": "设备ID。可选：rct-01(加氢反应器)、gc-01(气相色谱仪)、bal-01(分析天平)、ph-01(pH计)、pump-01(蠕动泵)",
        },
        "metric_name": {
            "type": "string",
            "description": "指标名（可选）。如 温度、压力、液位、pH、流速。留空返回该设备所有指标",
        },
        "start_time": {
            "type": "string",
            "description": "起始时间（可选）。相对分钟数（如 '30' 表示 30 分钟前）或 ISO 时间（如 '2026-08-10T15:00:00'）。默认 60 分钟前",
        },
        "end_time": {
            "type": "string",
            "description": "结束时间（可选）。ISO 时间，默认当前时间",
        },
    },
))
class QueryHardwareHistoryTool(BaseTool):
    """查询硬件设备历史遥测数据。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        device_id = kwargs.get("device_id", "").strip()
        if not device_id:
            return ToolResult(success=False, error="缺少 device_id 参数")

        metric_name = kwargs.get("metric_name", "").strip() or None
        try:
            start_dt = _parse_start_time(kwargs.get("start_time"))
            end_dt = _parse_end_time(kwargs.get("end_time"))
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        if end_dt < start_dt:
            return ToolResult(success=False, error="end_time 不能早于 start_time")

        try:
            from app.database.session import get_session_factory
            from app.models.tables import DeviceTelemetryHistory

            stmt = (
                select(DeviceTelemetryHistory)
                .where(DeviceTelemetryHistory.device_id == device_id)
                .where(DeviceTelemetryHistory.timestamp >= start_dt)
                .where(DeviceTelemetryHistory.timestamp <= end_dt)
            )
            if metric_name:
                stmt = stmt.where(DeviceTelemetryHistory.metric_name == metric_name)
            stmt = stmt.order_by(DeviceTelemetryHistory.timestamp.asc())

            session_factory = get_session_factory()
            async with session_factory() as session:
                result = await session.execute(stmt)
                rows = result.scalars().all()

            if not rows:
                return ToolResult(
                    success=False,
                    error=f"设备 {device_id} 在查询范围内没有遥测数据"
                    f"（{start_dt.isoformat()} ~ {end_dt.isoformat()}"
                    + (f"，指标 {metric_name}" if metric_name else "")
                    + "）。可先用 read_hardware 查看实时数据",
                )

            unit = rows[0].unit
            timestamps = [r.timestamp.isoformat() for r in rows]
            values = [float(r.metric_value) for r in rows]

            timestamps, values = _downsample(timestamps, values)

            return ToolResult(
                success=True,
                data={
                    "device_id": device_id,
                    "metric_name": metric_name or "all",
                    "unit": unit,
                    "count": len(rows),
                    "sampled_points": len(timestamps),
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "timestamps": timestamps,
                    "values": values,
                    "plot_hint": "可直接将 timestamps 作为 x、values 作为 y 调用 plot_chart 绘制趋势图",
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"查询历史数据失败: {exc}")


__all__ = [
    "ReadHardwareTool",
    "SendHardwareCommandTool",
    "QueryHardwareHistoryTool",
]
