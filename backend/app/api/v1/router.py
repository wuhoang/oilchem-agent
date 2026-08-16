"""
Aggregate v1 API router.

All v1 endpoints (future /api/v1/chat, /api/v1/tools, ...) are mounted
under the prefix defined in app.core.config.settings.api_v1_prefix.

AUTH_ENABLED=true 时，除 auth 路由外的所有端点强制登录。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.endpoints import (
    chat,
    db,
    experiments,
    files,
    hardware,
    health,
    llm,
    system,
    web,
)
from app.core.config import settings

# AUTH_ENABLED=true 时全量鉴权。
# auth 路由不在本聚合器内挂载（否则登录端点自身也要 token），
# 由 main.py 单独挂载。
_auth_deps = [Depends(get_current_user)] if settings.auth_enabled else []

api_v1_router = APIRouter(dependencies=_auth_deps)
api_v1_router.include_router(system.router, tags=["system"])
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(llm.router, tags=["llm"])
api_v1_router.include_router(files.router, tags=["files"])
api_v1_router.include_router(chat.router, tags=["chat"])
api_v1_router.include_router(db.router, tags=["db"])
api_v1_router.include_router(hardware.router, tags=["hardware"])
api_v1_router.include_router(web.router, tags=["web"])
api_v1_router.include_router(experiments.router, tags=["experiments"])

__all__ = ["api_v1_router"]
