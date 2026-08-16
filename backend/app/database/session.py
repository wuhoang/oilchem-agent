"""
SQLAlchemy 会话管理。

提供异步引擎、异步会话工厂和 FastAPI 依赖注入。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 延迟初始化
_engine = None
_async_session = None


def get_engine():
    """获取或创建异步引擎。"""
    global _engine
    if _engine is None:
        url = settings.database_url
        _engine = create_async_engine(
            url,
            echo=settings.db_echo,
            pool_pre_ping=True,
            future=True,
        )
        logger.bind(component="database").info(
            "Database engine created: {}", url
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取异步会话工厂。"""
    global _async_session
    if _async_session is None:
        engine = get_engine()
        _async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            future=True,
        )
    return _async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话。"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """初始化数据库。

    优先使用 Alembic 迁移历史表；随后对新增模型做 create_all 补建
    （幂等，不会覆盖已有表），最后填充种子数据。
    """
    import asyncio

    engine = get_engine()

    # 1. 运行 Alembic 迁移（处理已记录的历史表）
    try:
        from pathlib import Path

        import alembic.command
        import alembic.config

        def _run_migration() -> None:
            alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
            if alembic_ini.exists():
                alembic_cfg = alembic.config.Config(str(alembic_ini))
                alembic_cfg.set_main_option(
                    "sqlalchemy.url",
                    settings.database_url.replace("sqlite+aiosqlite:///", "sqlite:///"),
                )
                alembic.command.upgrade(alembic_cfg, "head")

        await asyncio.to_thread(_run_migration)
        logger.bind(component="database").info("Database migrated via Alembic")
    except Exception as exc:
        logger.bind(component="database").warning(
            "Alembic migration failed: {}", exc
        )

    # 2. 对迁移脚本未覆盖的新增模型做 create_all（幂等，已有表不受影响）
    from app.database.base import Base
    from app.models import _import_all_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.bind(component="database").debug("create_all check complete")

    # 3. 种子数据：仅在业务表为空时插入（幂等）
    await _seed_business_data()
    await _seed_users()


async def _seed_business_data() -> None:
    """在业务表为空时插入预设的示例数据（幂等）。"""
    from sqlalchemy import select

    from app.models.tables import (
        SEED_DEVICES,
        SEED_EXPERIMENTERS,
        SEED_EXPERIMENTS,
        SEED_MATERIALS,
        SEED_PROTOCOL_STEPS,
        SEED_PROTOCOLS,
        SEED_SAMPLES,
        Device,
        Experiment,
        Experimenter,
        Material,
        Protocol,
        ProtocolStep,
        Sample,
    )

    engine = get_engine()
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        # 实验表
        result = await session.execute(select(Experiment).limit(1))
        if result.first() is None:
            for row in SEED_EXPERIMENTS:
                session.add(Experiment(**row))
            logger.bind(component="database").info(
                "Seeded {} experiments", len(SEED_EXPERIMENTS)
            )

        # 样品表
        result = await session.execute(select(Sample).limit(1))
        if result.first() is None:
            for row in SEED_SAMPLES:
                session.add(Sample(**row))
            logger.bind(component="database").info(
                "Seeded {} samples", len(SEED_SAMPLES)
            )

        # 设备表
        result = await session.execute(select(Device).limit(1))
        if result.first() is None:
            for row in SEED_DEVICES:
                session.add(Device(**row))
            logger.bind(component="database").info(
                "Seeded {} devices", len(SEED_DEVICES)
            )

        # 实验员表
        result = await session.execute(select(Experimenter).limit(1))
        if result.first() is None:
            for row in SEED_EXPERIMENTERS:
                session.add(Experimenter(**row))
            logger.bind(component="database").info(
                "Seeded {} experimenters", len(SEED_EXPERIMENTERS)
            )

        # 方案表
        result = await session.execute(select(Protocol).limit(1))
        if result.first() is None:
            for row in SEED_PROTOCOLS:
                session.add(Protocol(**row))
            logger.bind(component="database").info(
                "Seeded {} protocols", len(SEED_PROTOCOLS)
            )

        # 方案步骤表
        result = await session.execute(select(ProtocolStep).limit(1))
        if result.first() is None:
            for row in SEED_PROTOCOL_STEPS:
                session.add(ProtocolStep(**row))
            logger.bind(component="database").info(
                "Seeded {} protocol_steps", len(SEED_PROTOCOL_STEPS)
            )

        # 物料表
        result = await session.execute(select(Material).limit(1))
        if result.first() is None:
            for row in SEED_MATERIALS:
                session.add(Material(**row))
            logger.bind(component="database").info(
                "Seeded {} materials", len(SEED_MATERIALS)
            )

        await session.commit()


async def _seed_users() -> None:
    """在 users 表为空时插入演示账号（幂等）。

    密码取自 .env（AUTH_ADMIN_PASSWORD / AUTH_OPERATOR_PASSWORD /
    AUTH_REVIEWER_PASSWORD），未配置时用默认值并在日志提示。
    """
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.models.tables import User

    engine = get_engine()
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        result = await session.execute(select(User).limit(1))
        if result.first() is not None:
            return

        default_admin = settings.auth_admin_password or "admin123"
        default_operator = settings.auth_operator_password or "operator123"
        default_reviewer = settings.auth_reviewer_password or "reviewer123"

        users = [
            User(username="admin", email="admin@oilchem.local", role="admin",
                 hashed_password=hash_password(default_admin)),
            User(username="operator", email="operator@oilchem.local", role="operator",
                 hashed_password=hash_password(default_operator)),
            User(username="reviewer", email="reviewer@oilchem.local", role="reviewer",
                 hashed_password=hash_password(default_reviewer)),
        ]
        for u in users:
            session.add(u)
        await session.commit()
        logger.bind(component="database").info(
            "Seeded {} demo users (admin/operator/reviewer)", len(users)
        )


async def close_db() -> None:
    """关闭数据库引擎。"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.bind(component="database").info("Database engine closed")


__all__ = [
    "get_engine",
    "get_session_factory",
    "get_db",
    "init_db",
    "close_db",
]
