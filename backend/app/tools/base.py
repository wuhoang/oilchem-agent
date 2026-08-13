"""
工具基类。

定义所有工具必须实现的抽象接口，以及工具的元数据模型。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 工具元数据
# ---------------------------------------------------------------------------

class ToolMetadata(BaseModel):
    """工具元数据，用于工具注册和 Agent 识别。"""

    name: str = Field(..., description="工具唯一名称（英文标识）")
    description: str = Field(..., description="工具功能描述，供 LLM 理解使用时机")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数的 JSON Schema 描述",
    )
    enabled: bool = Field(default=True, description="是否启用")


class ToolResult(BaseModel):
    """工具执行结果。"""

    success: bool = Field(..., description="是否执行成功")
    data: Any = Field(default=None, description="执行结果数据")
    error: str | None = Field(default=None, description="错误信息")


# ---------------------------------------------------------------------------
# 工具基类
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """工具抽象基类。

    所有自定义工具必须继承此类并实现 :meth:`execute`。

    Usage::

        class MyTool(BaseTool):
            metadata = ToolMetadata(name="my_tool", description="...")

            async def execute(self, **kwargs):
                return ToolResult(success=True, data="done")
    """

    metadata: ToolMetadata

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具。

        Parameters
        ----------
        **kwargs:
            工具参数，由 Agent 根据 metadata.parameters 构造。

        Returns
        -------
        ToolResult
            执行结果。
        """

    @property
    def name(self) -> str:
        """工具名称。"""
        return self.metadata.name

    @property
    def description(self) -> str:
        """工具描述。"""
        return self.metadata.description

    @property
    def enabled(self) -> bool:
        """是否启用。"""
        return self.metadata.enabled


__all__ = [
    "ToolMetadata",
    "ToolResult",
    "BaseTool",
]
