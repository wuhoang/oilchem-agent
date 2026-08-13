"""
app.tools — 工具系统。

自动导入内置工具以完成注册。
"""

from app.tools.base import BaseTool, ToolMetadata, ToolResult
from app.tools.registry import (
    register_tool,
    get_tool_class,
    list_tools,
    get_all_tool_classes,
    clear_registry,
)
from app.tools.manager import ToolManager

# 导入内置工具以触发装饰器注册
import app.tools.builtin.file_tools  # noqa: F401
import app.tools.builtin.hardware_tools  # noqa: F401
import app.tools.builtin.chart_tools  # noqa: F401
import app.tools.builtin.web_tools  # noqa: F401
import app.tools.builtin.office_tools  # noqa: F401

__all__ = [
    "BaseTool",
    "ToolMetadata",
    "ToolResult",
    "register_tool",
    "get_tool_class",
    "list_tools",
    "get_all_tool_classes",
    "clear_registry",
    "ToolManager",
]
