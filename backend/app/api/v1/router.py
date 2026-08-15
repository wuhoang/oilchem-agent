"""
Aggregate v1 API router.

All v1 endpoints (future /api/v1/chat, /api/v1/tools, ...) are mounted
under the prefix defined in app.core.config.settings.api_v1_prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import chat, db, experiments, files, hardware, health, llm, system, web

api_v1_router = APIRouter()
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
