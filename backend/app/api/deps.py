"""
认证/授权依赖。

get_current_user: 从 Authorization header 解析 JWT，查库返回当前用户。
require_role: 在 get_current_user 之上做角色校验（403 拒绝）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.tables import User


def _extract_token(authorization: str | None) -> str | None:
    """从 Authorization header 提取 Bearer token。"""
    if not authorization:
        return None
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


async def _user_from_token(db: AsyncSession, token: str) -> User:
    """解析 token 并返回用户；无效抛 401。"""
    payload = decode_access_token(token)
    if payload is None or payload.get("sub") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已停用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """认证依赖：从 Authorization header 校验令牌并返回当前用户。

    AUTH_ENABLED=false 时不校验（返回 None），保持开放模式。
    """
    if not settings.auth_enabled:
        return None  # type: ignore[return-value]

    token = _extract_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少登录令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _user_from_token(db, token)


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> tuple[User | None, bool]:
    """软认证依赖：返回 (当前用户, auth_enabled)，未登录不抛 401。

    与 get_current_user 区分：后者在 AUTH_ENABLED=true 且缺 token 时抛 401，
    用于受保护端点；本依赖用于 /auth/me 这类需区分「未登录」与「未开启认证」
    的探测端点。
    """
    if not settings.auth_enabled:
        return None, False
    token = _extract_token(authorization)
    if token is None:
        return None, True
    try:
        return await _user_from_token(db, token), True
    except HTTPException:
        # token 无效/过期也视为「已开启认证但未登录」
        return None, True


async def get_current_user_query(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Query()] = None,
) -> User:
    """认证依赖（SSE/WS 用）：从 ?token= 查询参数校验令牌。

    EventSource 无法携带 Authorization header，只能走 URL 参数。
    """
    if not settings.auth_enabled:
        return None  # type: ignore[return-value]

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少登录令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _user_from_token(db, token)


def require_role(*roles: str):
    """角色校验依赖工厂：允许指定角色访问，否则 403。"""

    async def _checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user is None:
            return None  # type: ignore[return-value]
        if current_user.role not in roles:
            logger.bind(component="auth").warning(
                "Forbidden: user={} role={} required={}",
                current_user.username,
                current_user.role,
                roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要角色: {', '.join(roles)}",
            )
        return current_user

    return _checker


__all__ = ["get_current_user", "get_current_user_query", "require_role"]