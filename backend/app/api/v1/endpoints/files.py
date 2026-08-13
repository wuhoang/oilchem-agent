"""
文件管理端点。

提供文件操作的 REST API 和文件变化监听的 WebSocket 端点。
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.tools.manager import ToolManager

router = APIRouter(tags=["files"])

# 工具管理器实例
_tool_manager = ToolManager()

OFFICE_EXTENSIONS = {".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt"}


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class ReadFileRequest(BaseModel):
    """读取文件请求。"""

    path: str = Field(..., description="文件绝对路径")
    start_line: int | None = Field(default=None, description="起始行号")
    end_line: int | None = Field(default=None, description="结束行号")


class WriteFileRequest(BaseModel):
    """写入文件请求。"""

    path: str = Field(..., description="文件绝对路径")
    content: str = Field(..., description="要写入的内容")


class AppendFileRequest(BaseModel):
    """追加文件请求。"""

    path: str = Field(..., description="文件绝对路径")
    content: str = Field(..., description="要追加的内容")


class ListFilesRequest(BaseModel):
    """列出文件请求。"""

    path: str = Field(..., description="目录绝对路径")
    recursive: bool = Field(default=False, description="是否递归")
    pattern: str | None = Field(default=None, description="过滤模式")


class DeleteFileRequest(BaseModel):
    """删除文件请求。"""

    path: str = Field(..., description="文件绝对路径")


class FileToolResponse(BaseModel):
    """文件工具响应。"""

    success: bool = Field(...)
    data: Any = Field(default=None)
    error: str | None = Field(default=None)


class WatchPathRequest(BaseModel):
    """注册监听路径请求。"""

    paths: list[str] = Field(..., description="要监听的目录路径列表")


class PreviewResponse(BaseModel):
    """文件预览响应。"""

    success: bool = Field(...)
    file_type: str = Field(default="text", description="文件类型：text/excel/word/ppt/image")
    content: Any = Field(default=None, description="预览内容")
    error: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# REST 端点
# ---------------------------------------------------------------------------

@router.post("/files/preview", response_model=PreviewResponse)
async def preview_file(req: ReadFileRequest) -> PreviewResponse:
    """预览文件内容。

    对 Office 文件（.xlsx/.docx/.pptx）返回结构化 JSON 数据，
    对其他文件返回文本内容。
    """
    file_path = req.path
    if not os.path.exists(file_path):
        return PreviewResponse(success=False, error=f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # Office 文件预览
    if ext in {".xlsx", ".xls"}:
        return await _preview_excel(file_path)
    elif ext in {".docx", ".doc"}:
        return await _preview_word(file_path)
    elif ext in {".pptx", ".ppt"}:
        return await _preview_ppt(file_path)
    # 图片文件
    elif ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"}:
        return PreviewResponse(
            success=True,
            file_type="image",
            content={"url": f"/api/v1/files/content?path={file_path}"},
        )
    # 文本文件
    else:
        result = await _tool_manager.execute(
            "read_file", path=file_path,
            start_line=req.start_line, end_line=req.end_line
        )
        if result.success:
            return PreviewResponse(
                success=True,
                file_type="text",
                content=result.data,
            )
        return PreviewResponse(success=False, error=result.error or "读取失败")


async def _preview_excel(file_path: str) -> PreviewResponse:
    """预览 Excel 文件。"""
    try:
        result = await _tool_manager.execute(
            "read_excel", file_path=file_path
        )
        if result.success and result.data:
            return PreviewResponse(
                success=True,
                file_type="excel",
                content=result.data,
            )
        return PreviewResponse(success=False, error=result.error or "Excel 读取失败")
    except Exception as e:
        return PreviewResponse(success=False, error=f"Excel 预览失败: {e}")


async def _preview_word(file_path: str) -> PreviewResponse:
    """预览 Word 文件。"""
    try:
        result = await _tool_manager.execute(
            "read_word", file_path=file_path, include_tables=True
        )
        if result.success and result.data:
            return PreviewResponse(
                success=True,
                file_type="word",
                content=result.data,
            )
        return PreviewResponse(success=False, error=result.error or "Word 读取失败")
    except Exception as e:
        return PreviewResponse(success=False, error=f"Word 预览失败: {e}")


async def _preview_ppt(file_path: str) -> PreviewResponse:
    """预览 PPT 文件。"""
    try:
        result = await _tool_manager.execute(
            "read_ppt", file_path=file_path
        )
        if result.success and result.data:
            return PreviewResponse(
                success=True,
                file_type="ppt",
                content=result.data,
            )
        return PreviewResponse(success=False, error=result.error or "PPT 读取失败")
    except Exception as e:
        return PreviewResponse(success=False, error=f"PPT 预览失败: {e}")


@router.post("/files/read", response_model=FileToolResponse)
async def read_file(req: ReadFileRequest) -> FileToolResponse:
    """读取文件内容。"""
    result = await _tool_manager.execute(
        "read_file", path=req.path, start_line=req.start_line, end_line=req.end_line
    )
    return FileToolResponse(**result.model_dump())


@router.post("/files/write", response_model=FileToolResponse)
async def write_file(req: WriteFileRequest) -> FileToolResponse:
    """写入文件（覆盖）。"""
    result = await _tool_manager.execute("write_file", path=req.path, content=req.content)
    return FileToolResponse(**result.model_dump())


@router.post("/files/append", response_model=FileToolResponse)
async def append_file(req: AppendFileRequest) -> FileToolResponse:
    """追加内容到文件。"""
    result = await _tool_manager.execute("append_file", path=req.path, content=req.content)
    return FileToolResponse(**result.model_dump())


@router.post("/files/list", response_model=FileToolResponse)
async def list_files(req: ListFilesRequest) -> FileToolResponse:
    """列出目录内容。"""
    result = await _tool_manager.execute(
        "list_files", path=req.path, recursive=req.recursive, pattern=req.pattern
    )
    return FileToolResponse(**result.model_dump())


@router.post("/files/delete", response_model=FileToolResponse)
async def delete_file(req: DeleteFileRequest) -> FileToolResponse:
    """删除文件。"""
    result = await _tool_manager.execute("delete_file", path=req.path)
    return FileToolResponse(**result.model_dump())


@router.get("/files/tools")
async def list_file_tools() -> dict:
    """列出所有文件相关工具。"""
    tools = _tool_manager.list_available_tools()
    return {"tools": tools}


# ---------------------------------------------------------------------------
# 文件监听管理端点
# ---------------------------------------------------------------------------

@router.post("/files/watch/start")
async def start_watching(req: WatchPathRequest) -> dict:
    """启动文件监听。"""
    from app.services.file_watcher import get_file_watcher

    watcher = get_file_watcher()
    await watcher.start(req.paths)
    return {"success": True, "message": f"Watching {len(req.paths)} paths"}


@router.post("/files/watch/stop")
async def stop_watching() -> dict:
    """停止文件监听。"""
    from app.services.file_watcher import get_file_watcher

    watcher = get_file_watcher()
    await watcher.stop()
    return {"success": True, "message": "File watcher stopped"}


# ---------------------------------------------------------------------------
# WebSocket 端点 — 文件变化推送
# ---------------------------------------------------------------------------

@router.websocket("/ws/files/events")
async def websocket_file_events(websocket: WebSocket) -> None:
    """文件变化事件 WebSocket。

    连接后将接收 JSON 格式的文件变化事件。
    事件格式::

        {
            "type": "file_change_batch",
            "total_events": 3,
            "aggregated": {
                "created": ["/path/to/new_file.txt"],
                "modified": ["/path/to/changed_file.txt"],
                "deleted": [],
                "moved": []
            },
            "timestamp": 1712500000.0
        }
    """
    from app.services.file_watcher import get_file_watcher, WATCHDOG_AVAILABLE

    await websocket.accept()

    if not WATCHDOG_AVAILABLE:
        await websocket.send_json(
            {"type": "error", "message": "watchdog not installed"}
        )
        await websocket.close()
        return

    watcher = get_file_watcher()
    event_queue = watcher.subscribe()

    # 发送初始确认
    await websocket.send_json(
        {"type": "connected", "message": "Listening for file changes..."}
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # 心跳
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except WebSocketDisconnect:
                    break
            except WebSocketDisconnect:
                break
    finally:
        watcher.unsubscribe(event_queue)


__all__ = ["router"]
