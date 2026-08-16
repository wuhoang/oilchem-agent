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
    STATUS_READY = "待执行"  # 设计预留，当前流程未启用（create→草稿，start→执行中）
    STATUS_RUNNING = "执行中"
    STATUS_PENDING_REVIEW = "待审核"  # 执行完成、报告生成后，等待实验员审核
    STATUS_COMPLETED = "已完成"  # 审核通过后的最终归档状态
    STATUS_REJECTED = "已驳回"  # 审核驳回
    STATUS_FAILED = "异常"
    STATUS_ABORTED = "中止"

    def __init__(self, driver_registry: DriverRegistry) -> None:
        self._drivers = driver_registry
        self._tasks: dict[str, asyncio.Task] = {}
        self._subscribers: set[asyncio.Queue] = set()
        logger.bind(component="orchestrator").info("Orchestrator initialized")

    def subscribe(self) -> asyncio.Queue:
        """订阅实验事件，返回一个 asyncio.Queue。"""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _publish(self, event: dict[str, Any]) -> None:
        """向所有订阅者广播事件（非阻塞）。"""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

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
                created_at=datetime.datetime.utcnow(),
            )
            session.add(exp)
            await session.commit()

        logger.bind(component="orchestrator").info(
            "实验创建: id={}, protocol={}", experiment_id, protocol_id
        )
        await self._audit(experiment_id, "create", f"方案={protocol_id} 操作员={operator_id}")
        return {"id": experiment_id, "name": name, "status": self.STATUS_DRAFT}

    async def start(self, experiment_id: str) -> None:
        """启动实验：复位设备 → 展开步骤 → 启动后台主循环。

        仅「草稿」/「待执行」状态的实验可启动；否则拒绝，防止对已有
        步骤的实验重复展开、重复执行。
        """
        if experiment_id in self._tasks:
            raise ValueError(f"实验 {experiment_id} 已在运行")

        from app.database.session import get_session_factory
        from app.models.tables import Experiment

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None:
                raise KeyError(f"实验不存在: {experiment_id}")
            if exp.status not in (self.STATUS_DRAFT, self.STATUS_READY):
                raise ValueError(
                    f"实验当前状态为「{exp.status}」，不能启动；仅「草稿」/「待执行」可启动"
                )

        await self._expand_steps(experiment_id)
        # 复位实验涉及的所有设备，避免上次实验残留状态（指标/曲线索引）
        await self._reset_devices(experiment_id)
        await self._set_status(experiment_id, self.STATUS_RUNNING)

        task = asyncio.create_task(self._run_loop(experiment_id))
        self._tasks[experiment_id] = task
        logger.bind(component="orchestrator").info(
            "实验启动: id={}", experiment_id
        )

    async def retry_step(self, experiment_id: str, step_order: int) -> None:
        """重试失败步骤：置回 running 并重启主循环。"""
        if experiment_id in self._tasks:
            raise ValueError(f"实验 {experiment_id} 已在运行，请勿重复操作")
        await self._reset_step(experiment_id, step_order)
        await self._set_status(experiment_id, self.STATUS_RUNNING)
        task = asyncio.create_task(self._run_loop(experiment_id))
        self._tasks[experiment_id] = task

    async def skip_step(self, experiment_id: str, step_order: int) -> None:
        """跳过步骤：标记 skipped，继续主循环。"""
        if experiment_id in self._tasks:
            raise ValueError(f"实验 {experiment_id} 已在运行，请勿重复操作")
        await self._mark_step_skipped(experiment_id, step_order)
        await self._set_status(experiment_id, self.STATUS_RUNNING)
        task = asyncio.create_task(self._run_loop(experiment_id))
        self._tasks[experiment_id] = task

    async def abort(self, experiment_id: str) -> None:
        """中止实验：取消任务 + 释放设备。

        仅「执行中」的实验可中止，防止误把「已完成」等终态实验改回「中止」。
        """
        from app.database.session import get_session_factory
        from app.models.tables import Experiment

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None:
                raise KeyError(f"实验不存在: {experiment_id}")
            if exp.status != self.STATUS_RUNNING:
                raise ValueError(
                    f"实验当前状态为「{exp.status}」，不能中止；仅「执行中」的实验可中止"
                )

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

    async def recover(self) -> int:
        """启动时恢复未完成的实验（重启前 status 为「执行中」）。

        进程重启后 _tasks 丢失，但实验状态留在数据库；此方法把卡在
        running 的步骤重置为 pending，并重新启动后台主循环。

        Returns
        -------
        int
            恢复的实验数量。
        """
        from app.database.session import get_session_factory
        from app.models.tables import Experiment, ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Experiment).where(Experiment.status == self.STATUS_RUNNING)
            )
            experiments = result.scalars().all()

        recovered = 0
        for exp in experiments:
            if exp.id in self._tasks:
                continue
            # 重置卡在 running 的步骤为 pending（进程中断时可能残留）
            async with factory() as session:
                result = await session.execute(
                    select(ExperimentStep).where(
                        ExperimentStep.experiment_id == exp.id,
                        ExperimentStep.status == "running",
                    )
                )
                for step in result.scalars().all():
                    step.status = "pending"
                    step.finished_at = None
                await session.commit()

            # 重启主循环
            task = asyncio.create_task(self._run_loop(exp.id))
            self._tasks[exp.id] = task
            recovered += 1
            logger.bind(component="orchestrator").info(
                "恢复未完成实验: id={}, status={}", exp.id, exp.status
            )

        if recovered:
            logger.bind(component="orchestrator").info(
                "已恢复 {} 个未完成实验", recovered
            )
        return recovered

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

    async def get_measurements(self, experiment_id: str) -> list[dict[str, Any]]:
        """查询实验测量数据（时间序列，按时间升序）。"""
        from app.database.session import get_session_factory
        from app.models.tables import Measurement

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Measurement)
                .where(Measurement.experiment_id == experiment_id)
                .order_by(Measurement.timestamp.asc())
            )
            measurements = result.scalars().all()

        return [
            {
                "metric_name": m.metric_name,
                "value": m.metric_value,
                "unit": m.unit,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in measurements
        ]

    async def approve(self, experiment_id: str, reviewer_id: str, reviewer_name: str, comment: str = "") -> None:
        """审核通过：实验从「待审核」转为「已完成」，记录审核人 ID/姓名与意见。"""
        import datetime as _dt

        from app.database.session import get_session_factory
        from app.models.tables import Experiment

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None:
                raise KeyError(f"实验不存在: {experiment_id}")
            if exp.status != self.STATUS_PENDING_REVIEW:
                raise ValueError(f"实验当前状态为「{exp.status}」，不能审核通过")
            exp.status = self.STATUS_COMPLETED
            exp.reviewed_by = reviewer_name
            exp.reviewed_by_id = reviewer_id
            exp.reviewed_at = _dt.datetime.utcnow()
            exp.review_comment = comment
            await session.commit()

        await self._audit(experiment_id, "approved", f"reviewer={reviewer_name}({reviewer_id}) comment={comment}")

    async def reject(self, experiment_id: str, reviewer_id: str, reviewer_name: str, comment: str = "") -> None:
        """审核驳回：实验转「已驳回」，记录审核人 ID/姓名与意见（可重新生成报告后再次审核）。"""
        import datetime as _dt

        from app.database.session import get_session_factory
        from app.models.tables import Experiment

        factory = get_session_factory()
        async with factory() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None:
                raise KeyError(f"实验不存在: {experiment_id}")
            if exp.status != self.STATUS_PENDING_REVIEW:
                raise ValueError(f"实验当前状态为「{exp.status}」，不能审核驳回")
            exp.status = self.STATUS_REJECTED
            exp.reviewed_by = reviewer_name
            exp.reviewed_by_id = reviewer_id
            exp.reviewed_at = _dt.datetime.utcnow()
            exp.review_comment = comment
            await session.commit()

        await self._audit(experiment_id, "rejected", f"reviewer={reviewer_name}({reviewer_id}) comment={comment}")

    # -- 内部 ---------------------------------------------------------------

    async def _reset_devices(self, experiment_id: str) -> None:
        """复位实验涉及的设备（幂等）。"""
        from app.database.session import get_session_factory
        from app.models.tables import ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ExperimentStep)
                .where(ExperimentStep.experiment_id == experiment_id)
            )
            steps = result.scalars().all()

        device_ids = {s.device_id for s in steps}
        for device_id in device_ids:
            driver = self._drivers.get(device_id)
            if driver is not None and hasattr(driver, "reset"):
                await driver.reset()
                logger.bind(component="orchestrator").info(
                    "设备复位: device={}", device_id
                )

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
                        # 所有步骤完成 → 先出结果和报告，再进入待审核（避免「已完成但报告缺失」）
                        await self._generate_result(experiment_id)
                        await self._generate_report(experiment_id)
                        await self._set_status(experiment_id, self.STATUS_PENDING_REVIEW)
                        logger.bind(component="orchestrator").info(
                            "实验完成（待审核）: id={}", experiment_id
                        )
                        break

                    step.status = "running"
                    step.started_at = datetime.datetime.utcnow()
                    await session.commit()

                # 执行步骤（阻塞，带超时）
                timeout = step.timeout_s if step.timeout_s and step.timeout_s > 0 else 300
                try:
                    result_step = await asyncio.wait_for(
                        self._execute_step(experiment_id, step),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    result_step = StepResult(
                        success=False,
                        status_code="timeout",
                        message=f"步骤超时（{timeout}s）",
                    )

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
                self._publish({
                    "type": "step_status",
                    "experiment_id": experiment_id,
                    "step_order": step.step_order,
                    "status": step.status,
                    "action": step.action,
                    "error": step.error_message,
                })

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
            await self._set_status(experiment_id, self.STATUS_ABORTED)
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
                    self._publish({
                        "type": "measurement",
                        "experiment_id": experiment_id,
                        "metric_name": metric_name,
                        "value": value,
                        "unit": unit,
                    })
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
        self._publish({"type": "experiment_status", "experiment_id": experiment_id, "status": status})

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

    async def _generate_report(self, experiment_id: str) -> None:
        """实验完成后自动生成报告（Word+Excel），失败只记日志不影响完成。"""
        try:
            from app.services.report_generator import generate_report

            result = await generate_report(experiment_id)

            from app.database.session import get_session_factory
            from app.models.tables import Experiment

            factory = get_session_factory()
            async with factory() as session:
                exp = await session.get(Experiment, experiment_id)
                if exp:
                    exp.report_path = result["word_path"]
                    await session.commit()
            logger.bind(component="orchestrator").info(
                "报告自动生成: id={}", experiment_id
            )
        except Exception as exc:
            logger.bind(component="orchestrator").error(
                "报告自动生成失败: id={}, error={}", experiment_id, exc
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
        """只释放当前实验占用的设备，不影响其他实验。"""
        from app.database.session import get_session_factory
        from app.models.tables import ExperimentStep

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ExperimentStep.device_id).where(
                    ExperimentStep.experiment_id == experiment_id
                ).distinct()
            )
            device_ids = [row[0] for row in result.all()]

        for device_id in device_ids:
            await self._drivers.release(device_id)


# 全局单例
_orchestrator: Orchestrator | None = None


def _interp_curve(keys: list[float], vals: list[float], n: int) -> list[float]:
    """把关键点线性插值成 n 个点的曲线。"""
    curve: list[float] = []
    for i in range(n):
        t = (i + 1) * (keys[-1] / n)
        for k in range(len(keys) - 1):
            if keys[k] <= t <= keys[k + 1]:
                x0, x1 = keys[k], keys[k + 1]
                y0, y1 = vals[k], vals[k + 1]
                curve.append(round(y0 + (y1 - y0) * (t - x0) / (x1 - x0), 2))
                break
    return curve


def _register_devices(registry: DriverRegistry) -> None:
    """从 hardware_simulation_data.json 加载真实油化设备。"""
    import json as _json
    from pathlib import Path

    from app.hardware.drivers import MockDriver

    data_file = Path(__file__).resolve().parents[3] / "hardware_info" / "hardware_simulation_data.json"
    try:
        with open(data_file, encoding="utf-8") as f:
            data = _json.load(f)
    except (OSError, ValueError) as exc:
        logger.bind(component="orchestrator").warning(
            "设备仿真数据加载失败，注册 0 台设备: {} ({})", data_file, exc
        )
        return

    devices = data.get("devices", {})

    # 高温高压失水仪（HTHP）—— 演示主场景，HTHP-01 带漏失量曲线
    for i, dev in enumerate(devices.get("高温高压失水仪", []), start=1):
        device_id = dev["device_id"]
        params = dev.get("parameters", {})
        leakage_raw = params.get("漏失量曲线", [])
        curve = None
        if leakage_raw:
            keys = [p["time_min"] for p in leakage_raw]
            vals = [p["leakage_ml"] for p in leakage_raw]
            curve = {"漏失量": _interp_curve(keys, vals, 30)}
        registry.register(
            device_id,
            MockDriver(
                device_id,
                metrics=[
                    {"name": "温度", "unit": "°C", "initial": 25},
                    {"name": "漏失量", "unit": "ml", "initial": 0},
                ],
                tick_s=0.2,
                curve=curve,
                name=f"高温高压失水仪 {device_id}",
                type_="hthp",
            ),
        )

    # 六速流变仪（Rheometer）
    for dev in devices.get("六速流变仪", []):
        device_id = dev["device_id"]
        params = dev.get("parameters", {})
        metrics = [
            {"name": k, "unit": "", "initial": v}
            for k, v in params.items() if isinstance(v, (int, float))
        ]
        registry.register(
            device_id,
            MockDriver(
                device_id,
                metrics=metrics,
                name=f"六速旋转粘度计 {device_id}",
                type_="rheometer",
            ),
        )

    # 稠化仪（Thickener）
    for dev in devices.get("稠化仪", []):
        device_id = dev["device_id"]
        params = dev.get("parameters", {})
        metrics = [
            {"name": k, "unit": "", "initial": v}
            for k, v in params.items() if isinstance(v, (int, float))
        ]
        registry.register(
            device_id,
            MockDriver(
                device_id,
                metrics=metrics,
                name=f"稠化仪 {device_id}",
                type_="thickener",
            ),
        )


def get_orchestrator() -> Orchestrator:
    """获取全局 Orchestrator 实例（从 json 加载真实油化设备）。"""
    global _orchestrator
    if _orchestrator is None:
        from app.hardware.drivers import DriverRegistry

        registry = DriverRegistry()
        _register_devices(registry)
        _orchestrator = Orchestrator(registry)
        logger.bind(component="orchestrator").info(
            "全局 Orchestrator 已初始化（{} 台真实设备）", len(registry.list_devices())
        )
    return _orchestrator


__all__ = ["Orchestrator", "get_orchestrator"]
