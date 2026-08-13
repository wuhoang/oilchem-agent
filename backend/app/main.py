"""
FastAPI application entry point.

Bootstraps:
  - structured logging (Loguru)
  - settings (Pydantic v2)
  - root banner endpoint (GET /)
  - health probe       (GET /health)
  - v1 API router      (prefix /api/v1)
  - file watcher service (auto-start on configured paths)
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Playwright sync API runs in background threads and needs the default
# ProactorEventLoop (Windows) for subprocess support.
# Do NOT set WindowsSelectorEventLoopPolicy here - it breaks Playwright.

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.constants import APP_NAME, APP_VERSION
from app.core.logger import logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.bind(component="app").info(
        "Starting {app} v{version} on http://{host}:{port} (env={env})",
        app=APP_NAME,
        version=APP_VERSION,
        host=settings.host,
        port=settings.port,
        env=settings.env,
    )

    # 初始化数据库
    try:
        from app.database import init_db

        await init_db()
        logger.bind(component="app").info("Database initialized")
    except Exception as exc:
        logger.bind(component="app").error("Database init failed: {}", exc)

    # 自动启动文件监听（如果配置了监听路径）
    watch_paths = [p.strip() for p in settings.file_watch_paths.split(",") if p.strip()]
    if watch_paths:
        try:
            from app.services.file_watcher import get_file_watcher

            watcher = get_file_watcher()
            await watcher.start(watch_paths)
            logger.bind(component="app").info(
                "File watcher auto-started for {} paths", len(watch_paths)
            )
        except Exception as exc:
            logger.bind(component="app").error(
                "Failed to auto-start file watcher: {}", exc
            )

    # 启动硬件遥测采集器
    collector = None
    try:
        from app.services.hardware_collector import get_hardware_collector

        collector = get_hardware_collector()
        await collector.start()
    except Exception as exc:
        logger.bind(component="app").error(
            "Failed to start hardware collector: {}", exc
        )

    yield

    # 关闭硬件遥测采集器
    if collector is not None:
        try:
            await collector.stop()
        except Exception:
            pass

    # 关闭文件监听
    try:
        from app.services.file_watcher import get_file_watcher

        watcher = get_file_watcher()
        await watcher.stop()
    except Exception:
        pass

    # 关闭数据库
    try:
        from app.database import close_db

        await close_db()
    except Exception:
        pass

    logger.bind(component="app").info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="OilChem Agent backend (Step 0 bootstrap).",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS — permissive defaults for local dev; tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root + health live at the top level (not under /api/v1).
    from app.api.v1.endpoints.health import router as health_router
    from app.api.v1.endpoints.system import router as system_router

    app.include_router(system_router)
    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug and not settings.is_production,
        log_config=None,  # let Loguru handle logging
    )


if __name__ == "__main__":
    main()
