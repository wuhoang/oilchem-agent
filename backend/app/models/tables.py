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
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")
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
# 种子数据（首次启动时插入）
# ---------------------------------------------------------------------------

SEED_EXPERIMENTS: list[dict] = [
    {"id": "EXP-001", "name": "柴油加氢脱硫评价", "operator": "张伟", "status": "进行中", "created_at": "2026-08-08 09:30"},
    {"id": "EXP-002", "name": "催化裂化催化剂筛选", "operator": "李娜", "status": "已完成", "created_at": "2026-08-07 14:12"},
    {"id": "EXP-003", "name": "重整原料油预处理", "operator": "王强", "status": "待开始", "created_at": "2026-08-09 08:00"},
    {"id": "EXP-004", "name": "pH 计校准实验", "operator": "赵敏", "status": "已完成", "created_at": "2026-08-06 16:45"},
    {"id": "EXP-005", "name": "气相色谱方法开发", "operator": "陈杰", "status": "进行中", "created_at": "2026-08-08 11:20"},
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
    "SEED_EXPERIMENTS",
    "SEED_SAMPLES",
    "SEED_DEVICES",
    "_import_all_models",
]
