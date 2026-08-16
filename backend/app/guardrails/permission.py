"""
权限控制。

实现基于角色的访问控制（RBAC），
控制用户对 Agent 功能和工具的访问权限。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from loguru import logger


class Role(str, Enum):
    """用户角色（与实验流程对齐）。"""

    ADMIN = "admin"      # 管理员：全部权限 + 账号管理
    OPERATOR = "operator"  # 操作员：聊天、建实验、跑实验
    REVIEWER = "reviewer"  # 审核人：审核实验报告
    USER = "user"        # 普通用户（兼容旧数据）
    VIEWER = "viewer"    # 只读用户（兼容旧数据）


# 角色权限映射
ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN: {"*"},  # 管理员拥有所有权限
    Role.OPERATOR: {
        "chat",
        "files.read",
        "files.write",
        "files.append",
        "files.list",
        "tools.list",
        "sessions.manage",
        "experiments.manage",
    },
    Role.REVIEWER: {
        "chat",
        "files.read",
        "files.list",
        "tools.list",
        "experiments.review",
    },
    Role.USER: {
        "chat",
        "files.read",
        "files.write",
        "files.append",
        "files.list",
        "tools.list",
        "sessions.manage",
    },
    Role.VIEWER: {
        "chat",
        "files.read",
        "files.list",
    },
}


class PermissionChecker:
    """权限检查器。

    基于角色检查用户是否有权访问特定功能。

    Usage::

        checker = PermissionChecker()
        has_perm = checker.has_permission("user", "files.write")
    """

    def __init__(self) -> None:
        self._permissions = dict(ROLE_PERMISSIONS)
        logger.bind(component="permissions").info("PermissionChecker initialized")

    def has_permission(self, role: str, permission: str) -> bool:
        """检查角色是否有权限。

        Parameters
        ----------
        role:
            用户角色。
        permission:
            权限标识（如 "files.write"）。

        Returns
        -------
        bool
            是否有权限。
        """
        allowed = self._permissions.get(role, set())
        if "*" in allowed:
            return True
        return permission in allowed

    def get_user_permissions(self, role: str) -> set[str]:
        """获取角色的所有权限。"""
        return self._permissions.get(role, set())

    def require_permission(self, role: str, permission: str) -> None:
        """要求用户必须拥有指定权限，否则抛出异常。

        Raises
        ------
        PermissionError
            如果用户没有权限。
        """
        if not self.has_permission(role, permission):
            logger.bind(component="permissions").warning(
                "Permission denied: role={}, permission={}", role, permission
            )
            raise PermissionError(
                f"Role '{role}' does not have permission '{permission}'"
            )

    def add_permission(self, role: str, permission: str) -> None:
        """为角色添加权限。"""
        if role not in self._permissions:
            self._permissions[role] = set()
        self._permissions[role].add(permission)

    def remove_permission(self, role: str, permission: str) -> None:
        """移除角色的权限。"""
        if role in self._permissions and permission in self._permissions[role]:
            self._permissions[role].discard(permission)


__all__ = ["Role", "PermissionChecker"]
