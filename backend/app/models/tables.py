"""
ORM 模型定义。

定义数据库表结构，包括用户、会话、消息、工具审计、
知识条目，以及业务表（实验记录、样品、设备）。
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# ---------------------------------------------------------------------------
# 用户表
# ---------------------------------------------------------------------------

class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


# ---------------------------------------------------------------------------
# 会话表
# ---------------------------------------------------------------------------

class Session(Base):
    """会话表。"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")


# ---------------------------------------------------------------------------
# 消息表
# ---------------------------------------------------------------------------

class Message(Base):
    """消息表。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_args: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_session_created", "session_id", "created_at"),)


# ---------------------------------------------------------------------------
# 工具审计表
# ---------------------------------------------------------------------------

class ToolAudit(Base):
    """工具调用审计表。"""

    __tablename__ = "tool_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    args: Mapped[str] = mapped_column(Text, default="", nullable=False)
    success: Mapped[bool] = mapped_column(nullable=False)
    result: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 知识条目表
# ---------------------------------------------------------------------------

class Knowledge(Base):
    """长期知识条目表。"""

    __tablename__ = "knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="unknown", nullable=False)
    tags: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 业务表：实验记录
# ---------------------------------------------------------------------------


class Experiment(Base):
    """实验记录表。"""

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="待开始")
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=True
    )
    # 追溯关联字段（可空，向后兼容已有数据）
    operator_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    protocol_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sample_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # 实验结果（JSON：摘要 + 图表 base64）
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 报告目录相对路径（backend/storage/reports/{id}）
    report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 业务表：样品
# ---------------------------------------------------------------------------


class Sample(Base):
    """样品表。"""

    __tablename__ = "samples"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    batch: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="在用")
    material_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 业务表：设备
# ---------------------------------------------------------------------------


class Device(Base):
    """设备表。"""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="在线")
    last_maintain: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 业务表：设备遥测历史
# ---------------------------------------------------------------------------


class DeviceTelemetryHistory(Base):
    """设备遥测历史记录。

    由后台采集器周期性写入，供 query_hardware_history 工具查询。
    """

    __tablename__ = "device_telemetry_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )


# ---------------------------------------------------------------------------
# 实验审计（M7）
# ---------------------------------------------------------------------------


class ExperimentAudit(Base):
    """实验审计事件表。"""

    __tablename__ = "experiment_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# 实验域主数据：实验员 / 方案 / 方案步骤
# ---------------------------------------------------------------------------


class Experimenter(Base):
    """实验员表。"""

    __tablename__ = "experimenters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="技术员")
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


class Protocol(Base):
    """实验设计（方案）表。"""

    __tablename__ = "protocols"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="草稿")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )


class ProtocolStep(Base):
    """方案步骤模板表。"""

    __tablename__ = "protocol_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    complete_criteria: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Material(Base):
    """物料主数据表。"""

    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ExperimentStep(Base):
    """实验步骤执行实例表（M2 运行时落库）。"""

    __tablename__ = "experiment_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    protocol_step_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    complete_criteria: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Measurement(Base):
    """实验测量数据点表。"""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    experiment_step_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# 种子数据（首次启动时插入）
# ---------------------------------------------------------------------------

SEED_EXPERIMENTS: list[dict] = [
    {"id": "EXP-001", "name": "柴油加氢脱硫评价", "operator": "张伟", "status": "进行中", "created_at": datetime.datetime(2026, 8, 8, 9, 30)},
    {"id": "EXP-002", "name": "催化裂化催化剂筛选", "operator": "李娜", "status": "已完成", "created_at": datetime.datetime(2026, 8, 7, 14, 12)},
    {"id": "EXP-003", "name": "重整原料油预处理", "operator": "王强", "status": "待开始", "created_at": datetime.datetime(2026, 8, 9, 8, 0)},
    {"id": "EXP-004", "name": "pH 计校准实验", "operator": "赵敏", "status": "已完成", "created_at": datetime.datetime(2026, 8, 6, 16, 45)},
    {"id": "EXP-005", "name": "气相色谱方法开发", "operator": "陈杰", "status": "进行中", "created_at": datetime.datetime(2026, 8, 8, 11, 20)},
]

SEED_SAMPLES: list[dict] = [
    {"code": "S-2026-0801", "name": "直馏柴油", "batch": "B-0801", "location": "A区-1层", "status": "在用"},
    {"code": "S-2026-0802", "name": "催化汽油", "batch": "B-0802", "location": "A区-2层", "status": "在用"},
    {"code": "S-2026-0803", "name": "重整生成油", "batch": "B-0803", "location": "B区-1层", "status": "留样"},
    {"code": "S-2026-0804", "name": "加氢尾油", "batch": "B-0804", "location": "B区-2层", "status": "待处置"},
]

SEED_DEVICES: list[dict] = [
    {"id": "R-101", "name": "加氢反应器", "model": "HC-500", "status": "在线", "last_maintain": "2026-07-15"},
    {"id": "GC-2030", "name": "气相色谱仪", "model": "GC-2030", "status": "在线", "last_maintain": "2026-08-01"},
    {"id": "XS205", "name": "分析天平", "model": "XS205", "status": "在线", "last_maintain": "2026-06-20"},
    {"id": "FE28", "name": "pH计", "model": "FE28", "status": "在线", "last_maintain": "2026-08-05"},
    {"id": "RP-100", "name": "蠕动泵", "model": "RP-100", "status": "离线", "last_maintain": "2026-05-10"},
]


SEED_EXPERIMENTERS: list[dict] = [
    {"id": "OP-001", "name": "张伟", "role": "研究员", "department": "钻井液组"},
    {"id": "OP-002", "name": "李娜", "role": "工程师", "department": "钻井液组"},
]

# 演示主场景：HTHP 高温高压失水仪实验
SEED_PROTOCOLS: list[dict] = [
    {
        "id": "PROTO-001",
        "name": "高温高压失水仪滤失量测试",
        "description": "按 GB/T 标准测定钻井液在高温高压条件下的滤失量，绘制漏失量-时间曲线。",
        "version": "v1",
        "status": "已发布",
    },
]

SEED_PROTOCOL_STEPS: list[dict] = [
    {
        "protocol_id": "PROTO-001",
        "step_order": 1,
        "device_id": "HTHP-01",
        "action": "set_temperature",
        "params": '{"target": 180, "ramp_rate": 2}',
        "timeout_s": 300,
        "complete_criteria": '{"type": "target_reached", "target": 180, "tolerance": 1}',
        "description": "升温至 180°C",
    },
    {
        "protocol_id": "PROTO-001",
        "step_order": 2,
        "device_id": "HTHP-01",
        "action": "hold",
        "params": '{"duration_s": 3}',
        "timeout_s": 10,
        "complete_criteria": '{"type": "hold_duration", "duration_s": 3}',
        "description": "恒温 180°C 保持（演示加速为 3 秒）",
    },
    {
        "protocol_id": "PROTO-001",
        "step_order": 3,
        "device_id": "HTHP-01",
        "action": "measure",
        "params": '{"metric_name": "漏失量", "count": 30}',
        "timeout_s": 60,
        "complete_criteria": '{"type": "measurement_count", "count": 30}',
        "description": "采集漏失量数据点（30 分钟）",
    },
]

SEED_MATERIALS: list[dict] = [
    {"id": "MAT-001", "name": "膨润土", "spec": "钻井级", "manufacturer": "通用", "unit": "kg"},
    {"id": "MAT-002", "name": "标准滤纸", "spec": "Ø90mm", "manufacturer": "通用", "unit": "张"},
]


def _import_all_models() -> None:
    """触发 SQLAlchemy 元数据收集。"""
    pass  # 模块级导入已自动注册


__all__ = [
    "User",
    "Session",
    "Message",
    "ToolAudit",
    "Knowledge",
    "Experiment",
    "Sample",
    "Device",
    "DeviceTelemetryHistory",
    "Experimenter",
    "Protocol",
    "ProtocolStep",
    "Material",
    "ExperimentStep",
    "Measurement",
    "ExperimentAudit",
    "SEED_EXPERIMENTS",
    "SEED_SAMPLES",
    "SEED_DEVICES",
    "SEED_EXPERIMENTERS",
    "SEED_PROTOCOLS",
    "SEED_PROTOCOL_STEPS",
    "SEED_MATERIALS",
    "_import_all_models",
]
