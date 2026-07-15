"""
GET / -> application banner.

This endpoint is intentionally NOT under /api/v1; it is the public
root banner used by health probes and frontend bootstrap detection.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings


router = APIRouter(tags=["system"])


class RootInfo(BaseModel):
    name: str
    version: str
    status: str


@router.get("/", response_model=RootInfo)
async def root() -> RootInfo:
    return RootInfo(
        name=settings.app_name,
        version=settings.version,
        status="running",
    )
