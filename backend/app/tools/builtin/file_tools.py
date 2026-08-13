"""
文件系统内置工具。

提供文件读取、写入、列表、追加、删除等操作，所有操作都受到
配置中 allowed_paths 的路径白名单限制，确保安全。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from app.tools.base import BaseTool, ToolMetadata, ToolResult
from app.tools.registry import register_tool


# ---------------------------------------------------------------------------
# 路径安全检查
# ---------------------------------------------------------------------------

# 项目根目录（通过代码相对定位，不依赖启动时的工作目录）
PROJECT_ROOT: Path = Path(__file__).resolve().parents[4]

def _get_allowed_paths() -> list[Path]:
    """获取允许操作的路径白名单。"""
    from app.core.config import settings

    raw = settings.file_allowed_paths.strip()
    if not raw:
        return []
    paths = []
    for p in raw.split(","):
        p = p.strip()
        if p:
            paths.append(Path(p).resolve())
    return paths


def _is_path_allowed(target: Path) -> bool:
    """检查目标路径是否在白名单内。"""
    allowed = _get_allowed_paths()
    if not allowed:
        return True  # 未配置白名单则允许所有路径（开发模式）
    resolved = target.resolve()
    return any(
        str(resolved).startswith(str(ap)) or resolved == ap
        for ap in allowed
    )


def _resolve_path(path_str: str) -> Path:
    """解析路径并检查安全性。"""
    if not path_str or not path_str.strip():
        path_str = str(PROJECT_ROOT)
    target = Path(path_str).expanduser().resolve()
    if not _is_path_allowed(target):
        raise PermissionError(
            f"Path '{target}' is not in the allowed paths. "
            f"Configure FILE_ALLOWED_PATHS in .env"
        )
    return target


def _is_text_file(path: Path) -> bool:
    """判断是否为文本文件（简单启发式检查）。"""
    text_extensions = {
        ".txt", ".md", ".csv", ".json", ".yaml", ".yml",
        ".xml", ".html", ".htm", ".css", ".js", ".ts",
        ".py", ".java", ".c", ".cpp", ".h", ".hpp",
        ".log", ".ini", ".cfg", ".toml", ".rst",
        ".tex", ".sql", ".sh", ".bat", ".ps1",
    }
    if path.suffix.lower() in text_extensions:
        return True
    # 尝试读取前几百字节，检测是否为二进制
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            # 包含 null 字节则视为二进制
            return b"\x00" not in chunk
    except (OSError, IOError):
        return False


# ---------------------------------------------------------------------------
# read_file — 读取文件内容
# ---------------------------------------------------------------------------

@register_tool(
    ToolMetadata(
        name="read_file",
        description="读取指定文件的文本内容。支持 CSV、JSON、Markdown、Python 等文本文件。对于二进制文件将返回元信息而非内容。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径（绝对路径）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从1开始，可选）",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（可选，不指定则读取全部）",
                },
            },
            "required": ["path"],
        },
    )
)
class ReadFileTool(BaseTool):
    """读取文件内容。"""

    async def execute(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            target = _resolve_path(path)
            if not target.exists():
                return ToolResult(
                    success=False, error=f"File not found: {target}"
                )
            if not target.is_file():
                return ToolResult(
                    success=False, error=f"Not a file: {target}"
                )

            if not _is_text_file(target):
                stat = target.stat()
                return ToolResult(
                    success=True,
                    data={
                        "path": str(target),
                        "is_binary": True,
                        "size_bytes": stat.st_size,
                        "message": "Binary file — content not returned for safety.",
                    },
                )

            content = target.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)

            if start_line is not None or end_line is not None:
                start = (start_line or 1) - 1
                end = end_line or len(lines)
                lines = lines[start:end]

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "content": "".join(lines),
                    "total_lines": len(content.splitlines()),
                    "read_lines": len(lines),
                },
            )
        except PermissionError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Read failed: {exc}")


# ---------------------------------------------------------------------------
# write_file — 写入文件
# ---------------------------------------------------------------------------

@register_tool(
    ToolMetadata(
        name="write_file",
        description="将内容写入指定文件。如果文件已存在则覆盖，不存在则创建。父目录必须已存在。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要写入的文件路径（绝对路径）",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文本内容",
                },
            },
            "required": ["path", "content"],
        },
    )
)
class WriteFileTool(BaseTool):
    """写入文件（覆盖）。"""

    async def execute(
        self, path: str, content: str, **kwargs: Any
    ) -> ToolResult:
        try:
            target = _resolve_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            logger.bind(component="tools").info(
                "Wrote file: {} ({} bytes)", target, len(content)
            )
            return ToolResult(
                success=True,
                data={"path": str(target), "bytes_written": len(content)},
            )
        except PermissionError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Write failed: {exc}")


# ---------------------------------------------------------------------------
# append_file — 追加内容到文件
# ---------------------------------------------------------------------------

@register_tool(
    ToolMetadata(
        name="append_file",
        description="将内容追加到指定文件末尾。如果文件不存在则创建。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要追加的文件路径（绝对路径）",
                },
                "content": {
                    "type": "string",
                    "description": "要追加的文本内容",
                },
            },
            "required": ["path", "content"],
        },
    )
)
class AppendFileTool(BaseTool):
    """追加内容到文件。"""

    async def execute(
        self, path: str, content: str, **kwargs: Any
    ) -> ToolResult:
        try:
            target = _resolve_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
            logger.bind(component="tools").info(
                "Appended to file: {} ({} bytes)", target, len(content)
            )
            return ToolResult(
                success=True,
                data={"path": str(target), "bytes_appended": len(content)},
            )
        except PermissionError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Append failed: {exc}")


# ---------------------------------------------------------------------------
# list_files — 列出目录内容
# ---------------------------------------------------------------------------

@register_tool(
    ToolMetadata(
        name="list_files",
        description="列出指定目录下的文件和子目录。返回每个条目的名称、类型和大小。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要列出的目录路径（绝对路径）",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出子目录内容",
                },
                "pattern": {
                    "type": "string",
                    "description": "文件过滤模式（glob 格式，如 *.csv）",
                },
            },
            "required": ["path"],
        },
    )
)
class ListFilesTool(BaseTool):
    """列出目录内容。"""

    async def execute(
        self,
        path: str,
        recursive: bool = False,
        pattern: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            target = _resolve_path(path)
            if not target.exists():
                return ToolResult(
                    success=False, error=f"Directory not found: {target}"
                )
            if not target.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {target}"
                )

            entries: list[dict[str, Any]] = []
            iterator = target.rglob("*") if recursive else target.iterdir()

            for entry in sorted(iterator):
                if pattern and not entry.match(pattern):
                    continue
                try:
                    stat = entry.stat()
                    entries.append(
                        {
                            "name": entry.name,
                            "path": str(entry),
                            "is_dir": entry.is_dir(),
                            "size_bytes": stat.st_size if entry.is_file() else 0,
                            "modified": stat.st_mtime,
                        }
                    )
                except OSError:
                    entries.append(
                        {
                            "name": entry.name,
                            "path": str(entry),
                            "is_dir": entry.is_dir(),
                            "size_bytes": 0,
                            "modified": 0,
                            "error": "Permission denied",
                        }
                    )

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "total": len(entries),
                    "entries": entries,
                },
            )
        except PermissionError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"List failed: {exc}")


# ---------------------------------------------------------------------------
# delete_file — 删除文件
# ---------------------------------------------------------------------------

@register_tool(
    ToolMetadata(
        name="delete_file",
        description="删除指定文件。仅支持删除文件，不支持删除目录（安全考虑）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要删除的文件路径（绝对路径）",
                },
            },
            "required": ["path"],
        },
    )
)
class DeleteFileTool(BaseTool):
    """删除文件。"""

    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        try:
            target = _resolve_path(path)
            if not target.exists():
                return ToolResult(
                    success=False, error=f"File not found: {target}"
                )
            if target.is_dir():
                return ToolResult(
                    success=False,
                    error="Cannot delete directories via delete_file. Use list_files to inspect first.",
                )
            target.unlink()
            logger.bind(component="tools").warning(
                "Deleted file: {}", target
            )
            return ToolResult(
                success=True,
                data={"path": str(target), "message": "File deleted"},
            )
        except PermissionError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Delete failed: {exc}")


__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "AppendFileTool",
    "ListFilesTool",
    "DeleteFileTool",
]
