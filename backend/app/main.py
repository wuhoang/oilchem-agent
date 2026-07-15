"""
FastAPI application entry point.

Bootstraps:
  - structured logging (Loguru)
  - settings (Pydantic v2)
  - root banner endpoint (GET /)
  - health probe       (GET /health)
  - v1 API router      (prefix /api/v1)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

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
    yield
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
