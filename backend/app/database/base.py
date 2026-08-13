"""
SQLAlchemy 声明式基类。

所有 ORM 模型都应继承此 Base。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass


__all__ = ["Base"]
