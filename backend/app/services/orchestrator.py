"""
编排引擎（M2）。

把一条实验方案变成一步步可执行、可跟踪、可异常处理的任务流，
驱动设备完成。引擎不感知设备真伪——只面向 M3 的 DeviceDriver 抽象接口。

- 实验状态机：draft → ready → running → completed / failed / aborted
- 步骤展开：start 时读 protocol_steps 实例化为 experiment_steps
- 主循环：逐步骤执行，设备占用，异常冻结 + 人工介入（重试/跳步/中止）
"""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.hardware.drivers.base import StepResult
from app.hardware.drivers.registry import DriverRegistry, BusyError


class Orchestrator:
    """实验编排引擎。

    Usage::

        orch = Orchestrator(driver_registry)
        experiment = await orch.create_experiment("PROTO-001", "OP-001", "S-001")
        await orch.start(experiment.id)
        progress = await orch.get_progress(experiment.id)
    """

    # 实验状态
    STATUS_DRAFT = "草稿"
    STATUS_READY = "待执行"
    STATUS_RUNNING = "执行中"
    STATUS_COMPLETED = "已完成"
    STATUS_FAILED = "异常"
    STATUS_ABORTED = "中止"

    def __init__(self, driver_registry: DriverRegistry) -> None:
        self._drivers = driver_registry
        self._tasks: dict[str, asyncio.Task] = {}
        logger.bind(component="orchestrator").info("Orchestrator initialized")

    # -- 实验生命周期 -------------------------------------------------------

    async def create_experiment(
        self,
        name: str,
        protocol_id: str,
        operator_id: str,
        sample_code: str | None = None,
    ) -> dict[str, Any]:
        """创建实验记录（状态 draft）。"""
        from app.database.session import get_session_factory
        from app.models.tables import Experiment, Protocol

        experiment_id = self._gen_id()
        factory = get_session_factory()
        async with factory() as session:
            proto = await session.get(Protocol, protocol_id)
            if proto is None:
                raise ValueError(f"方案不存在: {protocol_id}")

            exp = Experiment(
                id=experiment_id,
                name=name,
                operator=operator_id,
                operator_id=operator_id,
                protocol_id=protocol_id,
                sample_code=sample_code,
                status=self.STATUS_DRAFT,
                created_at=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            )
            session.add(exp)
            await session.commit()

        logger.bind(component="orchestrator").info(
            "实验创建: id={}, protocol={}", experiment_id, protocol_id
        )
        await self._audit(experiment_id, "create", f"方案={protocol_id} 操作员={operator_id}")
        return {"id": experiment_id, "name": name, "status": self.STATUS_DRAFT}

    async def start(self, experiment_id: str) -> None:
        """启动实验：展开步骤 + 启动后台主循环。"""
        if experiment_id in self._tasks:
            raise ValueError(f"实验 {experiment_id} 已在运行")

        await self._expand_steps(experiment_id)
        await self._set_status(experiment_id, self.STATUS_RUNNING)

        task = asyncio.create_task(self._run_loop(experiment_id))
        self._tasks[experiment_id] = task
        logger.bind(component="orchestrator").info(
            "实验启动: id={}", experiment_id
        )

    async def retry_step(self, experiment_id: str, step_order: int) -> None:
        """重试失败步骤：置回 running 并重启主循环。"""
        await self._reset_step(experiment_id, step_order)
        await self._set_status(experiment_id, self.STATUS_RUNNING)
        task = asyncio.create_task(self._run_loop(experiment_id))
        self._tasks[experiment_id] = task

    async def skip_step(self, experiment_id: str, step_order: int) -> None:
        """跳过步骤：标记 skipped，继续主循环。"""
        await self._mark_step_skipped(experiment_id, step_order)
        await self._set_status(experiment_id, self.STATUS_RUNNING)
        task = asyncio.create_task(self._run_loop(experiment_id))
        self._tasks[experiment_id] = task

    async def abort(self, experiment_id: str) -> None:
        """中止实验：取消任务 + 释放设备。"""
        task = self._tasks.pop(experiment_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._set_status(experiment_id, self.STATUS_ABORTED)
        await self._release_devices(experiment_id)
        logger.bind(component="orchestrator").info(
            "实验中止: id={}", experiment_id
        )

    # -- 查询 ---------------------------------------------------------------

    async def get_progress(self, experiment_id: str) -> dict[str, Any]:
        """获取实验进度快照。"""
        from app.database.session import get_session_factory
        from app.models.tables import Experiment, ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None:
                raise KeyError(f"实验不存在: {experiment_id}")
            result = await session.execute(
                select(ExperimentStep)
                .where(ExperimentStep.experiment_id == experiment_id)
                .order_by(ExperimentStep.step_order.asc())
            )
            steps = result.scalars().all()
            return {
                "experiment_id": experiment_id,
                "status": exp.status,
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

    # -- 内部 ---------------------------------------------------------------

    async def _expand_steps(self, experiment_id: str) -> None:
        """读 protocol_steps 实例化为 experiment_steps。"""
        from app.database.session import get_session_factory
        from app.models.tables import Experiment, ProtocolStep, ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None or exp.protocol_id is None:
                raise ValueError("实验缺少方案关联")

            result = await session.execute(
                select(ProtocolStep)
                .where(ProtocolStep.protocol_id == exp.protocol_id)
                .order_by(ProtocolStep.step_order.asc())
            )
            templates = result.scalars().all()

            for tpl in templates:
                step = ExperimentStep(
                    experiment_id=experiment_id,
                    protocol_step_id=tpl.id,
                    step_order=tpl.step_order,
                    device_id=tpl.device_id,
                    action=tpl.action,
                    params=tpl.params,
                    timeout_s=tpl.timeout_s,
                    complete_criteria=tpl.complete_criteria,
                    status="pending",
                )
                session.add(step)
            await session.commit()

        logger.bind(component="orchestrator").info(
            "步骤展开: experiment={}, {} steps", experiment_id, len(templates)
        )

    async def _run_loop(self, experiment_id: str) -> None:
        """主循环：逐步骤执行。"""
        from app.database.session import get_session_factory
        from app.models.tables import ExperimentStep, Measurement

        factory = get_session_factory()
        try:
            while True:
                # 取第一个未完成步骤
                async with factory() as session:
                    result = await session.execute(
                        select(ExperimentStep)
                        .where(ExperimentStep.experiment_id == experiment_id)
                        .where(ExperimentStep.status.in_(["pending", "running"]))
                        .order_by(ExperimentStep.step_order.asc())
                        .limit(1)
                    )
                    step = result.scalars().first()

                    if step is None:
                        # 所有步骤完成
                        await self._set_status(experiment_id, self.STATUS_COMPLETED)
                        await self._generate_result(experiment_id)
                        logger.bind(component="orchestrator").info(
                            "实验完成: id={}", experiment_id
                        )
                        break

                    step.status = "running"
                    step.started_at = datetime.datetime.utcnow()
                    await session.commit()

                # 执行步骤（阻塞）
                result_step = await self._execute_step(experiment_id, step)

                async with factory() as session:
                    step = await session.get(ExperimentStep, step.id)
                    if result_step.success:
                        step.status = "succeeded"
                    else:
                        step.status = "failed"
                        step.error_message = result_step.message
                    step.finished_at = datetime.datetime.utcnow()
                    await session.commit()

                await self._audit(
                    experiment_id,
                    "step_succeed" if result_step.success else "step_fail",
                    f"step={step.step_order} action={step.action}",
                )

                if not result_step.success:
                    await self._set_status(experiment_id, self.STATUS_FAILED)
                    logger.bind(component="orchestrator").warning(
                        "实验异常: id={}, step={}, error={}",
                        experiment_id, step.step_order, result_step.message,
                    )
                    break

        except asyncio.CancelledError:
            logger.bind(component="orchestrator").info(
                "实验主循环取消: id={}", experiment_id
            )
        except Exception as exc:
            logger.bind(component="orchestrator").error(
                "实验主循环异常: id={}, error={}", experiment_id, exc
            )
            await self._set_status(experiment_id, self.STATUS_FAILED)
        finally:
            self._tasks.pop(experiment_id, None)

    async def _execute_step(
        self, experiment_id: str, step: Any
    ) -> StepResult:
        """执行单个步骤：占用设备 → 执行 → 释放；measure 动作落库。

        若 complete_criteria 为 measurement_count，则循环采 N 个点，
        每次读遥测并落库，采满后返回成功。
        """
        from app.database.session import get_session_factory
        from app.models.tables import Measurement

        device_id = step.device_id
        try:
            driver = await self._drivers.acquire(device_id, experiment_id)
        except BusyError as exc:
            return StepResult(success=False, status_code="busy", message=str(exc))

        try:
            params = json.loads(step.params) if step.params else {}
            criteria = json.loads(step.complete_criteria) if step.complete_criteria else {}

            # measure + measurement_count：循环采点
            if step.action == "measure" and criteria.get("type") == "measurement_count":
                count = int(criteria.get("count", params.get("count", 1)))
                metric_name = params.get("metric_name", "值")
                unit = params.get("unit")
                factory = get_session_factory()
                for _ in range(count):
                    # 推进剧本曲线（若设备有该指标的曲线）
                    if hasattr(driver, "advance_curve"):
                        driver.advance_curve(metric_name)
                    # 从驱动读遥测，取目标指标
                    telemetry = await driver.read_telemetry()
                    value = None
                    for tp in telemetry:
                        if tp.metric_name == metric_name:
                            value = tp.value
                            break
                    if value is None:
                        value = 0.0
                    async with factory() as session:
                        session.add(
                            Measurement(
                                experiment_id=experiment_id,
                                experiment_step_id=step.id,
                                metric_name=metric_name,
                                metric_value=value,
                                unit=unit,
                            )
                        )
                        await session.commit()
                    await asyncio.sleep(0.3)
                return StepResult(success=True, message=f"已采 {count} 个数据点")

            # set_temperature/ramp：升温过程中采样温度点落库（温度曲线）
            if step.action in ("set_temperature", "ramp"):
                factory = get_session_factory()
                target = float(params.get("target", 0))
                # 记录初始温度
                telemetry_start = await driver.read_telemetry()
                for tp in telemetry_start:
                    if tp.metric_name == "温度":
                        async with factory() as session:
                            session.add(
                                Measurement(
                                    experiment_id=experiment_id,
                                    experiment_step_id=step.id,
                                    metric_name="温度",
                                    metric_value=tp.value,
                                    unit=tp.unit,
                                )
                            )
                            await session.commit()
                        break
                step_dict = {
                    "action": step.action,
                    "params": params,
                    "complete_criteria": criteria,
                    "timeout_s": step.timeout_s,
                }
                result = await driver.execute_step(step_dict)
                # 记录结束温度
                if result.success:
                    telemetry = await driver.read_telemetry()
                    for tp in telemetry:
                        if tp.metric_name == "温度":
                            async with factory() as session:
                                session.add(
                                    Measurement(
                                        experiment_id=experiment_id,
                                        experiment_step_id=step.id,
                                        metric_name="温度",
                                        metric_value=tp.value,
                                        unit=tp.unit,
                                    )
                                )
                                await session.commit()
                            break
                return result

            # 其他动作：交给驱动执行
            step_dict = {
                "action": step.action,
                "params": params,
                "complete_criteria": criteria,
                "timeout_s": step.timeout_s,
            }
            return await driver.execute_step(step_dict)
        finally:
            await self._drivers.release(device_id)

    # -- 辅助 ---------------------------------------------------------------

    @staticmethod
    def _gen_id() -> str:
        import uuid

        return "EXP-" + uuid.uuid4().hex[:8].upper()

    async def _set_status(self, experiment_id: str, status: str) -> None:
        from app.database.session import get_session_factory
        from app.models.tables import Experiment

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp:
                exp.status = status
                await session.commit()
        await self._audit(experiment_id, "status", status)

    async def _generate_result(self, experiment_id: str) -> None:
        """实验完成后自动生成结果：画漏失量曲线 + 摘要，存入 experiment.result。"""
        from app.database.session import get_session_factory
        from app.models.tables import Experiment, Measurement

        factory = get_session_factory()
        try:
            async with factory() as session:
                measurements = (
                    await session.execute(
                        select(Measurement)
                        .where(Measurement.experiment_id == experiment_id)
                        .order_by(Measurement.timestamp.asc())
                    )
                ).scalars().all()

                if not measurements:
                    return

                # 按指标名分组
                by_metric: dict[str, list[float]] = {}
                for m in measurements:
                    by_metric.setdefault(m.metric_name, []).append(m.metric_value)

                # 选数据点最多的指标作为主曲线（漏失量 30 点 > 温度 1 点）
                metric_name = max(by_metric.keys(), key=lambda k: len(by_metric[k]))
                values = by_metric[metric_name]
                x = list(range(1, len(values) + 1))

                from app.tools.builtin.chart_tools import PlotChartTool

                chart_result = await PlotChartTool().execute(
                    chart_type="plot",
                    x_data=x,
                    y_data=values,
                    title=f"实验 {experiment_id} {metric_name}曲线",
                    x_label="数据点",
                    y_label=metric_name,
                )

                result_data: dict[str, Any] = {
                    "summary": {
                        "metric_name": metric_name,
                        "points": len(values),
                        "max": max(values) if values else 0,
                        "min": min(values) if values else 0,
                        "final": values[-1] if values else 0,
                    },
                    "measurements": {
                        name: vals for name, vals in by_metric.items()
                    },
                }
                if chart_result.success and isinstance(chart_result.data, dict):
                    result_data["chart"] = {
                        "chart_type": chart_result.data.get("chart_type"),
                        "image_base64": chart_result.data.get("image_base64"),
                        "image_mime": chart_result.data.get("image_mime"),
                        "width": chart_result.data.get("width"),
                        "height": chart_result.data.get("height"),
                    }

                exp = await session.get(Experiment, experiment_id)
                if exp:
                    exp.result = json.dumps(result_data, ensure_ascii=False, default=str)
                    await session.commit()

                logger.bind(component="orchestrator").info(
                    "实验结果生成: id={}, 指标={}, 点={}",
                    experiment_id, metric_name, len(values),
                )
        except Exception as exc:
            logger.bind(component="orchestrator").error(
                "结果生成失败: {}", exc
            )

    async def _audit(self, experiment_id: str, event_type: str, detail: str = "") -> None:
        """写入一条实验审计事件。"""
        from app.database.session import get_session_factory
        from app.models.tables import ExperimentAudit

        factory = get_session_factory()
        try:
            async with factory() as session:
                session.add(
                    ExperimentAudit(
                        experiment_id=experiment_id,
                        event_type=event_type,
                        detail=detail,
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.bind(component="orchestrator").error(
                "审计写入失败: {}", exc
            )

    async def _reset_step(self, experiment_id: str, step_order: int) -> None:
        from app.database.session import get_session_factory
        from app.models.tables import ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ExperimentStep).where(
                    ExperimentStep.experiment_id == experiment_id,
                    ExperimentStep.step_order == step_order,
                )
            )
            step = result.scalars().first()
            if step:
                step.status = "pending"
                step.error_message = None
                await session.commit()

    async def _mark_step_skipped(self, experiment_id: str, step_order: int) -> None:
        from app.database.session import get_session_factory
        from app.models.tables import ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ExperimentStep).where(
                    ExperimentStep.experiment_id == experiment_id,
                    ExperimentStep.step_order == step_order,
                )
            )
            step = result.scalars().first()
            if step:
                step.status = "skipped"
                await session.commit()

    async def _release_devices(self, experiment_id: str) -> None:
        for device_id in self._drivers.list_devices():
            await self._drivers.release(device_id)


# 全局单例
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """获取全局 Orchestrator 实例（含默认 Mock 设备驱动注册）。"""
    global _orchestrator
    if _orchestrator is None:
        from app.hardware.drivers import DriverRegistry, MockDriver

        registry = DriverRegistry()
        # 演示主场景：HTHP 高温高压失水仪
        # 漏失量剧本曲线：7 个关键点线性插值成 30 个点（30 分钟），曲线更平滑
        _leakage_key = [0, 5, 10, 15, 20, 25, 30]
        _leakage_val = [0.0, 2.5, 4.8, 6.9, 8.7, 10.2, 11.5]
        leakage_curve: list[float] = []
        for i in range(30):
            t = i + 1  # 1..30 分钟
            # 线性插值
            for k in range(len(_leakage_key) - 1):
                if _leakage_key[k] <= t <= _leakage_key[k + 1]:
                    x0, x1 = _leakage_key[k], _leakage_key[k + 1]
                    y0, y1 = _leakage_val[k], _leakage_val[k + 1]
                    leakage_curve.append(round(y0 + (y1 - y0) * (t - x0) / (x1 - x0), 2))
                    break
        registry.register(
            "HTHP-01",
            MockDriver(
                "HTHP-01",
                metrics=[
                    {"name": "温度", "unit": "°C", "initial": 25},
                    {"name": "漏失量", "unit": "ml", "initial": 0},
                ],
                tick_s=0.2,
                curve={"漏失量": leakage_curve},
                name="高温高压失水仪",
                type_="hthp",
            ),
        )
        # 通用设备（与硬件面板一致，作为设备台账）
        registry.register(
            "rct-01",
            MockDriver(
                "rct-01",
                metrics=[
                    {"name": "温度", "unit": "°C", "initial": 185.3},
                    {"name": "压力", "unit": "MPa", "initial": 4.2},
                    {"name": "液位", "unit": "%", "initial": 62},
                ],
                name="加氢反应器 R-101",
                type_="reactor",
            ),
        )
        registry.register(
            "gc-01",
            MockDriver(
                "gc-01",
                metrics=[
                    {"name": "柱温", "unit": "°C", "initial": 220},
                    {"name": "载气压力", "unit": "MPa", "initial": 0.45},
                ],
                name="气相色谱仪 GC-2030",
                type_="chromatograph",
            ),
        )
        registry.register(
            "bal-01",
            MockDriver(
                "bal-01",
                metrics=[{"name": "当前重量", "unit": "g", "initial": 12.548}],
                name="分析天平 XS205",
                type_="balance",
            ),
        )
        registry.register(
            "ph-01",
            MockDriver(
                "ph-01",
                metrics=[
                    {"name": "pH", "unit": "", "initial": 7.42},
                    {"name": "温度", "unit": "°C", "initial": 25.3},
                ],
                name="pH计 FE28",
                type_="ph_meter",
            ),
        )
        registry.register(
            "pump-01",
            MockDriver(
                "pump-01",
                metrics=[{"name": "流速", "unit": "mL/min", "initial": 0}],
                name="蠕动泵 RP-100",
                type_="pump",
            ),
        )
        _orchestrator = Orchestrator(registry)
        logger.bind(component="orchestrator").info(
            "全局 Orchestrator 已初始化（Mock 设备注册）"
        )
    return _orchestrator


__all__ = ["Orchestrator", "get_orchestrator"]
