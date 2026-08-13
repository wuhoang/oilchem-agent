"""
工具注册表。

提供基于装饰器的工具注册机制，以及按名称查询、列举所有工具等功能。
"""

from __future__ import annotations

from typing import Type

from loguru import logger

from app.tools.base import BaseTool, ToolMetadata

# 全局注册表：工具名称 → 工具类
_TOOL_REGISTRY: dict[str, Type[BaseTool]] = {}


def register_tool(metadata: ToolMetadata):
    """工具注册装饰器。

    Usage::

        @register_tool(ToolMetadata(
            name="read_file",
            description="读取文件内容",
            parameters={"path": {"type": "string", "description": "文件路径"}}
        ))
        class ReadFileTool(BaseTool):
            async def execute(self, **kwargs):
                ...
    """

    def decorator(cls: Type[BaseTool]) -> Type[BaseTool]:
        tool_name = metadata.name
        if tool_name in _TOOL_REGISTRY:
            raise ValueError(f"Tool '{tool_name}' already registered")
        # 将 metadata 绑定到类
        cls.metadata = metadata
        _TOOL_REGISTRY[tool_name] = cls
        logger.bind(component="tools").debug("Registered tool: {}", tool_name)
        return cls

    return decorator


def get_tool_class(name: str) -> Type[BaseTool] | None:
    """根据名称获取工具类。"""
    return _TOOL_REGISTRY.get(name)


def list_tools() -> list[ToolMetadata]:
    """列出所有已注册工具的元数据。"""
    return [cls.metadata for cls in _TOOL_REGISTRY.values()]


def get_all_tool_classes() -> dict[str, Type[BaseTool]]:
    """获取所有工具类的映射表。"""
    return dict(_TOOL_REGISTRY)


def clear_registry() -> None:
    """清空注册表（主要用于测试）。"""
    _TOOL_REGISTRY.clear()


__all__ = [
    "register_tool",
    "get_tool_class",
    "list_tools",
    "get_all_tool_classes",
    "clear_registry",
]
