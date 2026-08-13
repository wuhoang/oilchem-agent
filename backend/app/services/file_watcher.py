"""
文件监听服务。

基于 watchdog 库实时监听指定文件夹的变化，当文件发生变更时
通过 WebSocket 主动推送给客户端。支持防抖（debounce）机制
以避免短时间内大量变化导致的事件风暴。
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from loguru import logger

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers.api import BaseObserver
    from watchdog.observers.polling import PollingObserver

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.bind(component="file_watcher").warning(
        "watchdog not installed. Run: pip install watchdog"
    )


# ---------------------------------------------------------------------------
# 事件处理器
# ---------------------------------------------------------------------------

class FileChangeHandler(FileSystemEventHandler):
    """文件变化事件处理器。

    将 watchdog 事件转换为统一的字典格式，放入异步队列。
    """

    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self._queue = queue

    def _enqueue(self, event_type: str, path: str, is_dir: bool) -> None:
        """将事件放入队列。"""
        try:
            self._queue.put_nowait(
                {
                    "type": event_type,
                    "path": path,
                    "is_directory": is_dir,
                    "timestamp": time.time(),
                }
            )
        except asyncio.QueueFull:
            logger.bind(component="file_watcher").warning(
                "Event queue is full, dropping event: {} {}", event_type, path
            )

    def on_created(self, event: FileSystemEvent) -> None:
        self._enqueue("created", event.src_path, event.is_directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._enqueue("modified", event.src_path, event.is_directory)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._enqueue("deleted", event.src_path, event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._enqueue("moved", event.src_path, event.is_directory)


# ---------------------------------------------------------------------------
# 防抖处理器
# ---------------------------------------------------------------------------

class DebouncedEventProcessor:
    """防抖事件处理器。

    将短时间内的多个事件合并为一个汇总事件，避免事件风暴。
    """

    def __init__(self, debounce_ms: int = 2000) -> None:
        self._debounce_ms = debounce_ms
        self._buffer: list[dict[str, Any]] = []
        self._last_flush = 0.0

    def add(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """添加事件并返回需要立即处理的事件列表。

        Returns
        -------
        list[dict]
            需要处理的事件列表（可能包含之前缓冲的事件）。
        """
        now = time.time()
        self._buffer.append(event)

        # 超过防抖窗口则刷新
        if (now - self._last_flush) * 1000 >= self._debounce_ms:
            return self.flush()

        return []

    def flush(self) -> list[dict[str, Any]]:
        """立即刷新缓冲区，返回所有缓冲的事件。"""
        events = self._buffer
        self._buffer = []
        self._last_flush = time.time()
        return events


# ---------------------------------------------------------------------------
# 文件监听服务
# ---------------------------------------------------------------------------

class FileWatcherService:
    """文件监听服务。

    管理 watchdog Observer 的生命周期，提供事件分发能力。

    Usage::

        service = FileWatcherService()
        await service.start(["/path/to/watch"])
        async for event in service.subscribe():
            print(event)
        await service.stop()
    """

    def __init__(self) -> None:
        self._observer: BaseObserver | None = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers: list[asyncio.Queue] = []
        self._debouncer = DebouncedEventProcessor()
        self._running = False
        self._dispatch_task: asyncio.Task | None = None

    async def start(self, watch_paths: list[str]) -> None:
        """启动文件监听。

        Parameters
        ----------
        watch_paths:
            要监听的目录路径列表。
        """
        if not WATCHDOG_AVAILABLE:
            logger.bind(component="file_watcher").error(
                "watchdog is not installed. Run: pip install watchdog"
            )
            return

        if self._running:
            logger.bind(component="file_watcher").warning(
                "FileWatcherService is already running"
            )
            return

        handler = FileChangeHandler(self._queue)
        self._observer = PollingObserver(timeout=1.0)

        for path_str in watch_paths:
            path = Path(path_str)
            if not path.exists():
                logger.bind(component="file_watcher").warning(
                    "Watch path does not exist, skipping: {}", path
                )
                continue
            self._observer.schedule(handler, str(path), recursive=True)
            logger.bind(component="file_watcher").info(
                "Watching: {}", path
            )

        self._observer.start()
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.bind(component="file_watcher").info(
            "FileWatcherService started ({} paths)", len(watch_paths)
        )

    async def stop(self) -> None:
        """停止文件监听。"""
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            self._dispatch_task = None
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        logger.bind(component="file_watcher").info("FileWatcherService stopped")

    def subscribe(self) -> asyncio.Queue:
        """订阅文件变化事件。

        Returns
        -------
        asyncio.Queue
            事件队列，消费者从该队列读取事件。
        """
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        logger.bind(component="file_watcher").debug(
            "New subscriber added (total={})", len(self._subscribers)
        )
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """取消订阅。"""
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def _dispatch_loop(self) -> None:
        """事件分发循环。

        从主队列读取事件，进行防抖处理，然后分发给所有订阅者。
        """
        while self._running:
            try:
                raw_event = await asyncio.wait_for(
                    self._queue.get(), timeout=0.5
                )
                to_process = self._debouncer.add(raw_event)

                if to_process:
                    aggregated = self._aggregate_events(to_process)
                    for sub_q in self._subscribers:
                        try:
                            sub_q.put_nowait(aggregated)
                        except asyncio.QueueFull:
                            pass
            except asyncio.TimeoutError:
                # 定期刷新防抖缓冲区
                pending = self._debouncer.flush()
                if pending:
                    aggregated = self._aggregate_events(pending)
                    for sub_q in self._subscribers:
                        try:
                            sub_q.put_nowait(aggregated)
                        except asyncio.QueueFull:
                            pass
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.bind(component="file_watcher").error(
                    "Dispatch loop error: {}", exc
                )

    @staticmethod
    def _aggregate_events(events: list[dict[str, Any]]) -> dict[str, Any]:
        """将多个事件聚合为一个汇总事件。"""
        created = [e for e in events if e["type"] == "created"]
        modified = [e for e in events if e["type"] == "modified"]
        deleted = [e for e in events if e["type"] == "deleted"]
        moved = [e for e in events if e["type"] == "moved"]

        return {
            "type": "file_change_batch",
            "total_events": len(events),
            "aggregated": {
                "created": [e["path"] for e in created],
                "modified": [e["path"] for e in modified],
                "deleted": [e["path"] for e in deleted],
                "moved": [e["path"] for e in moved],
            },
            "timestamp": time.time(),
        }


# 全局单例
_file_watcher: FileWatcherService | None = None


def get_file_watcher() -> FileWatcherService:
    """获取全局 FileWatcherService 实例。"""
    global _file_watcher
    if _file_watcher is None:
        _file_watcher = FileWatcherService()
    return _file_watcher


__all__ = [
    "FileWatcherService",
    "FileChangeHandler",
    "DebouncedEventProcessor",
    "get_file_watcher",
    "WATCHDOG_AVAILABLE",
]
