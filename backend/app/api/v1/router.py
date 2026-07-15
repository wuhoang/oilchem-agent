"""
Aggregate v1 API router.

All v1 endpoints (future /api/v1/chat, /api/v1/tools, ...) are mounted
under the prefix defined in app.core.config.settings.api_v1_prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health, system

api_v1_router = APIRouter()
api_v1_router.include_router(system.router, tags=["system"])
api_v1_router.include_router(health.router, tags=["health"])

__all__ = ["api_v1_router"]
