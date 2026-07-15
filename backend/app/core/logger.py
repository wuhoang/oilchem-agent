"""
Centralized Loguru configuration.

Format: time | level | module | message
Sinks : console (colored) + logs/app.log (plain, rotation 10 MB, retention 14 days)
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import LOGS_DIR, settings
from app.core.constants import APP_NAME


# Reset default handler so format strictly follows the spec.
logger.remove()


CONSOLE_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

FILE_FORMAT: str = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
)


def _build_log_file() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / "app.log"


def setup_logging() -> None:
    """Configure loguru sinks. Safe to call multiple times."""
    logger.remove()

    logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=settings.log_level.upper(),
        colorize=True,
        enqueue=False,
    )

    logger.add(
        str(_build_log_file()),
        format=FILE_FORMAT,
        level=settings.log_level.upper(),
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=False,
    )

    logger.bind(component="bootstrap").info(
        "Logger initialized for {app} (env={env}, level={level})",
        app=APP_NAME,
        env=settings.env,
        level=settings.log_level.upper(),
    )


# Configure at import time so the rest of the codebase can use `logger`
# without explicitly calling setup_logging.
setup_logging()


__all__ = ["logger", "setup_logging"]
