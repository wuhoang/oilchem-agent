"""
认证端点。

POST /auth/login — 账号密码换 JWT 令牌（限流：5 次/5 分钟/IP）
GET  /auth/me     — 当前登录用户信息
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.core.security import create_access_token, verify_password
from app.database.session import get_db
from app.models.tables import User

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# 简单内存限流（登录专用，进程重启清零，对演示场景足够）
# ---------------------------------------------------------------------------

_LOGIN_MAX_ATTEMPTS: int = 5
_LOGIN_WINDOW_S: float = 300.0  # 5 分钟

_login_failures: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    """检查 IP 是否超出登录失败限额，超出抛 429。"""
    now = time.monotonic()
    attempts = _login_failures[ip]
    # 清理过期记录
    _login_failures[ip] = [t for t in attempts if now - t < _LOGIN_WINDOW_S]
    if len(_login_failures[ip]) >= _LOGIN_MAX_ATTEMPTS:
        logger.bind(component="auth").warning("Rate limit hit: ip={}", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {_LOGIN_WINDOW_S / 60:.0f} 分钟后再试",
        )


def _record_failure(ip: str) -> None:
    """记录一次登录失败。"""
    _login_failures[ip].append(time.monotonic())


def _clear_failures(ip: str) -> None:
    """登录成功后清除该 IP 的失败记录。"""
    _login_failures.pop(ip, None)


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
async def login(
    request: LoginRequest,
    req: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """账号密码登录，签发 JWT 令牌。"""
    client_ip = req.client.host if req.client else "unknown"
    _check_rate_limit(client_ip)

    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(request.password, user.hashed_password):
        _record_failure(client_ip)
        logger.bind(component="auth").warning(
            "Login failed: username={} ip={}", request.username, client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        _record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用",
        )

    _clear_failures(client_ip)
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