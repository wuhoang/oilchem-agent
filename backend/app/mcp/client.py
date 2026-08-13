"""
MCP (Model Context Protocol) 集成框架。

提供 MCP Server 客户端能力，使 Agent 能够连接外部系统
（如 DCS、ERP、实时数据库等）并获取数据。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger


class MCPClient:
    """MCP 客户端。

    连接 MCP Server 并调用其工具。

    Usage::

        client = MCPClient("http://mcp-server:8080")
        tools = await client.list_tools()
        result = await client.call_tool("get_sensor_data", {"tag": "P101"})
    """

    def __init__(self, server_url: str, name: str = "default") -> None:
        self._server_url = server_url.rstrip("/")
        self._name = name
        self._tools: list[dict[str, Any]] = []
        logger.bind(component="mcp").info(
            "MCPClient initialized: name={}, url={}", name, server_url
        )

    async def list_tools(self) -> list[dict[str, Any]]:
        """列出 MCP Server 提供的工具。"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._server_url}/tools")
                response.raise_for_status()
                data = response.json()
                self._tools = data.get("tools", [])
                return self._tools
        except Exception as exc:
            logger.bind(component="mcp").error(
                "Failed to list MCP tools: {}", exc
            )
            return []

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """调用 MCP 工具。

        Parameters
        ----------
        tool_name:
            工具名称。
        arguments:
            工具参数。

        Returns
        -------
        dict
            工具调用结果。
        """
        import httpx

        payload = {
            "name": tool_name,
            "arguments": arguments or {},
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._server_url}/tools/call",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.bind(component="mcp").error(
                "MCP tool call failed: {}/{} - {}",
                self._name,
                tool_name,
                exc,
            )
            return {"error": str(exc)}

    @property
    def name(self) -> str:
        """客户端名称。"""
        return self._name

    @property
    def tools(self) -> list[dict[str, Any]]:
        """已缓存的工具列表。"""
        return self._tools


class MCPManager:
    """MCP 管理器。

    管理多个 MCP 客户端实例。

    Usage::

        mgr = MCPManager()
        mgr.add_server("dcs", "http://dcs-mcp:8080")
        tools = await mgr.list_all_tools()
    """

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}
        logger.bind(component="mcp").info("MCPManager initialized")

    def add_server(self, name: str, server_url: str) -> MCPClient:
        """添加 MCP Server。"""
        client = MCPClient(server_url, name)
        self._clients[name] = client
        logger.bind(component="mcp").info(
            "MCP server added: name={}, url={}", name, server_url
        )
        return client

    def remove_server(self, name: str) -> None:
        """移除 MCP Server。"""
        if name in self._clients:
            del self._clients[name]
            logger.bind(component="mcp").info("MCP server removed: {}", name)

    def get_client(self, name: str) -> MCPClient | None:
        """获取指定 MCP 客户端。"""
        return self._clients.get(name)

    def list_servers(self) -> list[str]:
        """列出所有已配置的 MCP Server。"""
        return list(self._clients.keys())

    async def list_all_tools(self) -> list[dict[str, Any]]:
        """列出所有 MCP Server 提供的工具。"""
        all_tools = []
        for name, client in self._clients.items():
            tools = await client.list_tools()
            for tool in tools:
                tool["mcp_server"] = name
            all_tools.extend(tools)
        return all_tools

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """调用指定 MCP Server 的工具。"""
        client = self._clients.get(server_name)
        if client is None:
            return {"error": f"MCP server '{server_name}' not found"}
        return await client.call_tool(tool_name, arguments)


__all__ = ["MCPClient", "MCPManager"]
