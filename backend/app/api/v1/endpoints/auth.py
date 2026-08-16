"""
认证端点。

POST /auth/login — 账号密码换 JWT 令牌
GET  /auth/me     — 当前登录用户信息
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.core.security import create_access_token, verify_password
from app.database.session import get_db
from app.models.tables import User

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class LoginResponse(BaseModel):
    """登录响应。"""

    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> LoginResponse:
    """账号密码登录，签发 JWT 令牌。"""
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(request.password, user.hashed_password):
        logger.bind(component="auth").warning(
            "Login failed: username={}", request.username
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用",
        )

    token = create_access_token(
        subject=str(user.id), role=user.role, username=user.username
    )
    logger.bind(component="auth").info(
        "Login success: username={} role={}", user.username, user.role
    )
    return LoginResponse(
        access_token=token,
        user={"id": user.id, "username": user.username, "role": user.role},
    )


@router.get("/auth/me")
async def me(
    auth: Annotated[tuple[User | None, bool], Depends(get_current_user_optional)],
) -> dict:
    """返回当前登录用户信息与认证开关状态（未登录时 user 为 null）。"""
    current_user, auth_enabled = auth
    if current_user is None:
        return {"user": None, "auth_enabled": auth_enabled}
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "email": current_user.email,
        },
        "auth_enabled": auth_enabled,
    }