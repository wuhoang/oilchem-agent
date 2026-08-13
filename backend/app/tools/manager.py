"""
工具管理器。

负责工具的查找、实例化和执行，是 Agent 调用工具的入口。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.tools.base import BaseTool, ToolResult
from app.tools.registry import get_tool_class, list_tools


class ToolManager:
    """工具管理器。

    Usage::

        manager = ToolManager()
        result = await manager.execute("read_file", path="/data/report.csv")
    """

    def __init__(self) -> None:
        logger.bind(component="tools").info(
            "ToolManager initialized with {} tools", len(list_tools())
        )

    def get_tool(self, name: str) -> BaseTool | None:
        """根据名称获取工具实例。"""
        tool_cls = get_tool_class(name)
        if tool_cls is None:
            return None
        return tool_cls()

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """执行指定工具。

        Parameters
        ----------
        name:
            工具名称。
        **kwargs:
            传递给工具的参数。

        Returns
        -------
        ToolResult
            执行结果。
        """
        tool = self.get_tool(name)
        if tool is None:
            logger.bind(component="tools").error("Tool not found: {}", name)
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found. Available: {[t.name for t in list_tools()]}",
            )

        if not tool.enabled:
            logger.bind(component="tools").warning("Tool is disabled: {}", name)
            return ToolResult(success=False, error=f"Tool '{name}' is disabled")

        logger.bind(component="tools").debug(
            "Executing tool: {} (args={})", name, kwargs
        )
        try:
            result = await tool.execute(**kwargs)
            if result.success:
                logger.bind(component="tools").debug(
                    "Tool {} succeeded", name
                )
            else:
                logger.bind(component="tools").warning(
                    "Tool {} failed: {}", name, result.error
                )
            return result
        except Exception as exc:
            logger.bind(component="tools").error(
                "Tool {} raised exception: {}", name, exc
            )
            return ToolResult(success=False, error=str(exc))

    def list_available_tools(self) -> list[dict[str, Any]]:
        """列出所有可用工具的描述信息（供 Agent 使用）。"""
        return [
            {
                "name": m.name,
                "description": m.description,
                "parameters": m.parameters,
            }
            for m in list_tools()
            if m.enabled
        ]


__all__ = ["ToolManager"]
