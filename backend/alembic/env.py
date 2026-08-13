# -*- coding: utf-8 -*-
"""Alembic environment configuration.

This module is loaded by Alembic to configure migration behavior.
It sets up the SQLAlchemy metadata target and database connection.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == "win32":
    import locale
    try:
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    except locale.Error:
        pass

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Path setup — ensure backend/ is on sys.path
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Models — import all ORM models so metadata is fully populated
# ---------------------------------------------------------------------------
from app.database.base import Base
import app.models.tables  # noqa: F401 — triggers model registration

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Database URL — resolve from settings or alembic.ini
# ---------------------------------------------------------------------------

def _get_sync_database_url() -> str:
    """获取用于迁移的同步数据库 URL。

    应用使用 aiosqlite（异步），但 Alembic 需要同步驱动。
    如果配置了 sqlite+aiosqlite，则转换为 sqlite。
    """
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url.replace("sqlite+aiosqlite:///", "sqlite:///")

    # 从 settings 获取
    try:
        from app.core.config import settings
        raw = settings.database_url
        return raw.replace("sqlite+aiosqlite:///", "sqlite:///")
    except Exception:
        return "sqlite:///./oilchem_agent.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = _get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "qmark"},
        compare_type=True,
        render_as_batch=True,  # SQLite 需要 batch 模式
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    This creates an Engine and associates a connection with the context.
    """
    url = _get_sync_database_url()
    config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,  # SQLite 需要 batch 模式
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
