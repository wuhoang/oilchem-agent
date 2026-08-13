"""
网页浏览与表单填写工具。

使用 Playwright 同步 API 在专用后台线程中运行，通过任务队列避免 Windows 事件循环限制和 greenlet 跨线程问题。
支持：
- 打开网页、截图
- 识别页面元素（输入框、按钮等）
- 自动填写表单（按索引）
- 智能填表（按字段名/描述自动匹配）
- 提取页面文本内容
"""

from __future__ import annotations

import asyncio
import base64
import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from app.tools.base import BaseTool, ToolMetadata, ToolResult
from app.tools.registry import register_tool

# 项目本地浏览器路径（相对于 backend/）
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_LOCAL_BROWSERS_PATH = str(_BACKEND_ROOT / ".playwright-browsers")


class _SyncBrowserManager:
    """同步 Playwright 浏览器管理器（专用后台线程 + 任务队列）。"""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._thread: threading.Thread | None = None
        self._task_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()
        self._started = threading.Event()
        self._stop_event = threading.Event()

    def start(self) -> None:
        """启动专用后台线程。"""
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait(timeout=30)
        if not self._started.is_set():
            raise RuntimeError("浏览器启动超时")

    def _run_loop(self) -> None:
        """后台线程主循环：初始化浏览器并处理任务。"""
        try:
            self._init_browser()
            self._started.set()
            logger.bind(component="web").info("浏览器后台线程已启动")

            while not self._stop_event.is_set():
                try:
                    task = self._task_queue.get(timeout=0.5)
                    if task is None:
                        break
                    fn, args, kwargs, result_event = task
                    try:
                        result = fn(self._browser, *args, **kwargs)
                        self._result_queue.put(("ok", result))
                    except Exception as exc:
                        self._result_queue.put(("error", exc))
                    result_event.set()
                except queue.Empty:
                    continue
        except Exception as exc:
            logger.bind(component="web").error("浏览器后台线程异常: {}", exc)
            self._started.set()
            self._result_queue.put(("error", exc))
        finally:
            self._cleanup()

    def _init_browser(self) -> None:
        """在后台线程中初始化浏览器。"""
        try:
            from playwright.sync_api import sync_playwright

            # 设置 Playwright 浏览器路径
            pw_browsers_path = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
            if os.path.isdir(pw_browsers_path):
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = pw_browsers_path
            else:
                os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _LOCAL_BROWSERS_PATH)

            logger.bind(component="web").info(
                "PLAYWRIGHT_BROWSERS_PATH={}", os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
            )

            self._playwright = sync_playwright().start()
            launch_options: dict[str, Any] = {"headless": True}
            errors: list[str] = []

            # 策略列表：依次尝试不同的启动方式
            strategies = [
                ("Playwright default", lambda: self._playwright.chromium.launch(**launch_options)),
                ("Channel: chrome", lambda: self._playwright.chromium.launch(**launch_options, channel="chrome")),
                ("Channel: msedge", lambda: self._playwright.chromium.launch(**launch_options, channel="msedge")),
            ]

            # 添加自定义路径策略
            chrome_exe = _find_chrome_executable()
            if chrome_exe:
                strategies.append((
                    f"Executable: {chrome_exe}",
                    lambda exe=chrome_exe: self._playwright.chromium.launch(**launch_options, executable_path=exe)
                ))

            for name, launcher in strategies:
                try:
                    logger.bind(component="web").info("Trying: {}", name)
                    self._browser = launcher()
                    logger.bind(component="web").info("Browser launched via: {}", name)
                    return
                except Exception as exc:
                    errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:200]}")
                    logger.bind(component="web").warning(
                        "Strategy failed: {} - {}", name, str(exc)[:200]
                    )

            # 所有策略都失败
            error_detail = "\n".join(errors)
            raise RuntimeError(
                f"Playwright 浏览器启动失败。所有策略均失败:\n{error_detail}\n"
                f"建议: python -m playwright install chromium"
            )

        except ImportError:
            raise RuntimeError(
                "Playwright 未安装。请运行: pip install playwright"
            )

    def _cleanup(self) -> None:
        """清理浏览器资源。"""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def execute(self, fn: Callable, *args, **kwargs) -> Any:
        """在后台线程中执行任务并返回结果（同步）。"""
        if not self._started.is_set():
            raise RuntimeError("浏览器未启动")

        result_event = threading.Event()
        self._task_queue.put((fn, args, kwargs, result_event))
        result_event.wait(timeout=60)

        try:
            status, value = self._result_queue.get_nowait()
            if status == "ok":
                return value
            raise value
        except queue.Empty:
            raise RuntimeError("任务执行超时")

    def stop(self) -> None:
        """停止后台线程。"""
        self._stop_event.set()
        self._task_queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


def _find_chrome_executable() -> str | None:
    """在项目本地或系统中查找 Chrome/Chromium 可执行文件路径。"""
    candidates = []

    # 项目本地 Playwright 路径
    for build_dir in ["chromium-1169", "chromium_headless_shell-1169"]:
        chrome_root = os.path.join(_LOCAL_BROWSERS_PATH, build_dir, "chrome-win")
        if os.path.isdir(chrome_root):
            for fname in ["chrome.exe", "headless_shell.exe"]:
                fpath = os.path.join(chrome_root, fname)
                if os.path.isfile(fpath):
                    candidates.append(fpath)

    # 系统 Playwright 安装路径
    pw_base = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
    if os.path.isdir(pw_base):
        try:
            for entry in os.listdir(pw_base):
                entry_path = os.path.join(pw_base, entry)
                if os.path.isdir(entry_path) and entry.startswith("chromium"):
                    chrome_root = os.path.join(entry_path, "chrome-win")
                    if os.path.isdir(chrome_root):
                        for fname in ["chrome.exe", "headless_shell.exe"]:
                            fpath = os.path.join(chrome_root, fname)
                            if os.path.isfile(fpath):
                                candidates.append(fpath)
        except OSError:
            pass

    # Windows 系统 Chrome
    candidates.extend([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ])

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            logger.bind(component="web").debug("Found Chrome at: {}", candidate)
            return candidate
    return None


# 全局同步浏览器管理器
_sync_browser_manager: _SyncBrowserManager | None = None
_sync_browser_lock = asyncio.Lock()


async def _get_sync_manager() -> _SyncBrowserManager:
    """获取同步浏览器管理器（单例）。"""
    global _sync_browser_manager
    async with _sync_browser_lock:
        if _sync_browser_manager is None:
            _sync_browser_manager = _SyncBrowserManager()
            # 启动专用后台线程
            await asyncio.to_thread(_sync_browser_manager.start)
    return _sync_browser_manager


async def _run_in_thread(task_fn: Callable, *args, **kwargs) -> Any:
    """在后台线程中运行同步任务（自动获取管理器）。"""
    manager = await _get_sync_manager()
    # 使用 manager.execute 在专用线程中执行任务
    return await asyncio.to_thread(manager.execute, task_fn, *args, **kwargs)


# ---------------------------------------------------------------------------
# 同步辅助函数（在后台线程中执行）
# ---------------------------------------------------------------------------

def _sync_collect_form_elements(page) -> dict[str, Any]:
    """收集页面上的所有表单元素信息（同步）。"""
    return page.evaluate("""() => {
        const inputs = [];
        document.querySelectorAll('input, textarea, select').forEach((el, i) => {
            let labelText = '';
            if (el.id) {
                const label = document.querySelector(`label[for="${el.id}"]`);
                if (label) labelText = label.textContent.trim();
            }
            if (!labelText && el.closest('label')) {
                labelText = el.closest('label').textContent.trim();
            }

            inputs.push({
                index: i,
                tag: el.tagName.toLowerCase(),
                type: el.type || el.tagName.toLowerCase(),
                name: el.name || '',
                id: el.id || '',
                placeholder: el.placeholder || '',
                label: labelText,
                visible: el.offsetParent !== null,
                value: el.value || '',
            });
        });

        const buttons = [];
        document.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"]').forEach((el, i) => {
            buttons.push({
                index: i,
                tag: el.tagName.toLowerCase(),
                text: (el.textContent.trim() || el.value || '').substring(0, 50),
                id: el.id || '',
                class: (el.className || '').toString().substring(0, 80),
                visible: el.offsetParent !== null,
                type: el.type || '',
            });
        });

        return { inputs, buttons };
    }""")


def _match_field(target_name: str, inputs: list[dict]) -> dict | None:
    """根据字段名/描述匹配页面表单元素。"""
    target = target_name.lower().strip()
    target_no_space = target.replace(" ", "")

    # 精确匹配 name
    for inp in inputs:
        if inp.get("name", "").lower() == target:
            return inp

    # 精确匹配 id
    for inp in inputs:
        if inp.get("id", "").lower() == target:
            return inp

    # 精确匹配 placeholder
    for inp in inputs:
        if inp.get("placeholder", "").lower() == target:
            return inp

    # 精确匹配 label 文本
    for inp in inputs:
        if inp.get("label", "").lower() == target:
            return inp

    # 包含匹配 name/id/placeholder/label
    for inp in inputs:
        for field in ["name", "id", "placeholder", "label"]:
            val = inp.get(field, "").lower()
            if val and (target in val or val in target_no_space):
                return inp

    # 关键词匹配
    keywords_map = {
        "username": ["user", "name", "account", "login", "用户名", "账号"],
        "user": ["user", "name", "account", "login", "用户名", "账号"],
        "password": ["pass", "pwd", "密码", "password"],
        "pass": ["pass", "pwd", "密码", "password"],
        "email": ["email", "mail", "邮箱"],
        "phone": ["phone", "mobile", "手机", "电话"],
        "phone_number": ["phone", "mobile", "手机", "电话"],
        "temperature": ["temp", "温度", "temperature"],
        "pressure": ["press", "压力", "pressure"],
        "sample": ["sample", "样品", "样本"],
        "concentration": ["conc", "浓度", "concentration"],
        "volume": ["vol", "体积", "volume"],
        "weight": ["weight", "mass", "重量", "质量"],
        "date": ["date", "日期"],
        "time": ["time", "时间"],
        "title": ["title", "标题"],
        "description": ["desc", "description", "描述"],
    }

    keywords = keywords_map.get(target, [target])
    for inp in inputs:
        for field in ["name", "id", "placeholder", "label"]:
            val = inp.get(field, "").lower()
            for kw in keywords:
                kw_lower = kw.lower()
                if val and kw_lower in val:
                    return inp

    return None


def _sync_fill_field_by_info(page, input_info: dict, value: str) -> bool:
    """根据元素信息填写字段（同步）。"""
    tag = input_info.get("tag", "input")
    idx = input_info.get("index", 0)

    selectors = []

    name = input_info.get("name", "")
    if name:
        selectors.append(f'[name="{name}"]')

    el_id = input_info.get("id", "")
    if el_id:
        selectors.append(f'#{el_id}')

    placeholder = input_info.get("placeholder", "")
    if placeholder:
        selectors.append(f'[placeholder="{placeholder}"]')

    if tag == "input":
        selectors.append(f"input:nth-of-type({idx + 1})")
    elif tag == "textarea":
        selectors.append(f"textarea:nth-of-type({idx + 1})")
    elif tag == "select":
        selectors.append(f"select:nth-of-type({idx + 1})")

    for selector in selectors:
        try:
            page.fill(selector, str(value), timeout=3000)
            return True
        except Exception:
            continue

    return False


def _sync_click_submit_button(page, buttons: list[dict]) -> bool:
    """智能查找并点击提交按钮（同步）。"""
    submit_keywords = ["submit", "login", "sign", "登录", "提交", "确认", "确定", "开始", "save", "保存"]

    for btn in buttons:
        if btn.get("type") == "submit":
            try:
                page.click(f'button:nth-of-type({btn["index"] + 1})', timeout=3000)
                return True
            except Exception:
                pass

    for btn in buttons:
        btn_text = btn.get("text", "").lower()
        btn_class = btn.get("class", "").lower()
        for kw in submit_keywords:
            if kw.lower() in btn_text or kw.lower() in btn_class:
                try:
                    tag = btn.get("tag", "button")
                    selector = f'{tag}:nth-of-type({btn["index"] + 1})'
                    page.click(selector, timeout=3000)
                    return True
                except Exception:
                    continue

    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


def _sync_take_screenshot(page) -> dict[str, Any]:
    """截图并返回 base64 编码（同步）。"""
    screenshot_bytes = page.screenshot(type="png")
    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    return {
        "screenshot_base64": screenshot_b64,
        "screenshot_mime": "image/png",
        "width": 1280,
        "height": 800,
    }


# ---------------------------------------------------------------------------
# 工具实现
# ---------------------------------------------------------------------------

@register_tool(ToolMetadata(
    name="browse_webpage",
    description=(
        "打开网页并返回页面内容、表单元素信息和截图。"
        "可用于登录系统前的页面分析、提取页面文本等。"
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "要打开的网页 URL，如 https://example.com/login",
        },
        "timeout": {
            "type": "integer",
            "description": "超时时间（毫秒），默认 30000",
        },
    },
))
class BrowseWebpageTool(BaseTool):
    """浏览网页并返回页面内容和截图。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "").strip()
        if not url:
            return ToolResult(success=False, error="缺少 url 参数")

        timeout = int(kwargs.get("timeout", 30000))

        try:
            manager = await _get_sync_manager()

            def _browse(browser, target_url: str, timeout_ms: int) -> dict:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                try:
                    page.goto(target_url, timeout=timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)

                    title = page.title()
                    text_content = page.evaluate("""() => {
                        const clone = document.body.cloneNode(true);
                        clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
                        return clone.textContent.replace(/\\s+/g, ' ').trim().substring(0, 5000);
                    }""")

                    form_elements = _sync_collect_form_elements(page)
                    shot = _sync_take_screenshot(page)

                    return {
                        "success": True,
                        "url": page.url,
                        "title": title,
                        "text_content": text_content,
                        "form_elements": form_elements,
                        **shot,
                    }
                finally:
                    page.close()

            result = await asyncio.to_thread(manager.execute, _browse, url, timeout)
            return ToolResult(success=True, data=result)

        except Exception as e:
            logger.bind(component="web").error("browse_webpage failed: {}", e)
            return ToolResult(success=False, error=f"浏览网页失败: {e}")


@register_tool(ToolMetadata(
    name="smart_fill_form",
    description=(
        "智能网页填表工具。自动打开网页，识别表单字段，"
        "按字段名/描述匹配并填写数据，然后提交表单。"
        "支持：用户名密码登录、按字段名批量填写、自动识别提交按钮。"
        "LLM 可直接使用此工具完成端到端的网页操作，无需先 browse 再 fill。"
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "要操作的网页 URL",
        },
        "username": {
            "type": "string",
            "description": "用户名（登录用），自动匹配 username/account 字段",
        },
        "password": {
            "type": "string",
            "description": "密码（登录用），自动匹配 password 字段",
        },
        "field_mapping": {
            "type": "object",
            "description": "字段映射 {字段名: 值}，如 {'温度': '25', 'pressure': '1.5', '样品编号': 'EXP-001'}。"
                           "字段名可以是 name/id/placeholder/label 的任意一种，支持中英文。",
        },
        "auto_submit": {
            "type": "boolean",
            "description": "填写完成后是否自动提交（默认 true）",
        },
        "timeout": {
            "type": "integer",
            "description": "超时时间（毫秒），默认 30000",
        },
    },
))
class SmartFillFormTool(BaseTool):
    """智能网页填表工具 — LLM 端到端调用。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "").strip()
        username = kwargs.get("username", "")
        password = kwargs.get("password", "")
        field_mapping = kwargs.get("field_mapping", {})
        auto_submit = kwargs.get("auto_submit", True)
        timeout = int(kwargs.get("timeout", 30000))

        if not url:
            return ToolResult(success=False, error="缺少 url 参数")

        if not username and not field_mapping:
            return ToolResult(success=False, error="请提供 username/password 或 field_mapping")

        try:
            manager = await _get_sync_manager()

            def _smart_fill(browser, target_url, user, pwd, fmap, auto_sub, timeout_ms):
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                try:
                    page.goto(target_url, timeout=timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(800)

                    form_elements = _sync_collect_form_elements(page)
                    inputs = form_elements.get("inputs", [])
                    buttons = form_elements.get("buttons", [])

                    filled_fields = []
                    failed_fields = []

                    # 处理用户名密码登录
                    if user or pwd:
                        login_mapping = {}
                        if user:
                            login_mapping["username"] = user
                        if pwd:
                            login_mapping["password"] = pwd

                        for field_name, field_value in login_mapping.items():
                            matched = _match_field(field_name, inputs)
                            if matched:
                                ok = _sync_fill_field_by_info(page, matched, str(field_value))
                                if ok:
                                    filled_fields.append({
                                        "field": field_name,
                                        "matched_to": matched.get("name") or matched.get("id") or f"index_{matched.get('index')}",
                                        "value": str(field_value)[:20] + "***" if field_name == "password" else str(field_value),
                                    })
                                else:
                                    failed_fields.append({"field": field_name, "reason": "fill failed"})
                            else:
                                failed_fields.append({"field": field_name, "reason": "not found"})

                    # 处理字段映射
                    if fmap:
                        for field_name, field_value in fmap.items():
                            matched = _match_field(str(field_name), inputs)
                            if matched:
                                ok = _sync_fill_field_by_info(page, matched, str(field_value))
                                if ok:
                                    filled_fields.append({
                                        "field": field_name,
                                        "matched_to": matched.get("name") or matched.get("id") or f"index_{matched.get('index')}",
                                        "value": str(field_value),
                                    })
                                else:
                                    failed_fields.append({"field": field_name, "reason": "fill failed"})
                            else:
                                failed_fields.append({"field": field_name, "reason": "not found on page"})

                    # 自动提交
                    submitted = False
                    if auto_sub:
                        submitted = _sync_click_submit_button(page, buttons)
                        if submitted:
                            page.wait_for_timeout(2000)

                    current_url = page.url
                    title = page.title()
                    shot = _sync_take_screenshot(page)

                    return {
                        "success": True,
                        "url": current_url,
                        "title": title,
                        "fields_filled": len(filled_fields),
                        "filled_fields": filled_fields,
                        "failed_fields": failed_fields,
                        "submitted": submitted,
                        **shot,
                        "message": f"成功填写 {len(filled_fields)} 个字段，失败 {len(failed_fields)} 个",
                    }
                finally:
                    page.close()

            result = await asyncio.to_thread(
                manager.execute, _smart_fill, url, username, password, field_mapping, auto_submit, timeout
            )
            return ToolResult(success=True, data=result)

        except Exception as exc:
            logger.bind(component="web").error("smart_fill_form failed: {}", exc)
            return ToolResult(success=False, error=f"智能填表失败: {exc}")


@register_tool(ToolMetadata(
    name="fill_webform",
    description=(
        "在网页上按索引填写表单（用于需要精确控制的场景）。"
        "推荐优先使用 smart_fill_form 工具，它支持按字段名自动匹配。"
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "要操作的网页 URL",
        },
        "form_data": {
            "type": "object",
            "description": "表单填写数据，格式：{'index': 'value'}，如 {'0': 'admin', '1': 'password'}",
        },
        "click_button_index": {
            "type": "integer",
            "description": "要点击的按钮索引（可选）",
        },
        "username": {
            "type": "string",
            "description": "用户名快捷方式",
        },
        "password": {
            "type": "string",
            "description": "密码快捷方式",
        },
        "submit": {
            "type": "boolean",
            "description": "填写完成后是否自动提交（默认 true）",
        },
        "timeout": {
            "type": "integer",
            "description": "超时时间（毫秒），默认 30000",
        },
    },
))
class FillWebformTool(BaseTool):
    """按索引填写表单（保留兼容）。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "").strip()
        form_data = kwargs.get("form_data", {})
        username = kwargs.get("username", "")
        password = kwargs.get("password", "")
        click_button_index = kwargs.get("click_button_index", None)
        auto_submit = kwargs.get("submit", True)
        timeout = int(kwargs.get("timeout", 30000))

        if not url:
            return ToolResult(success=False, error="缺少 url 参数")

        try:
            manager = await _get_sync_manager()

            def _fill_form(browser, target_url, fdata, user, pwd, btn_idx, auto_sub, timeout_ms):
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                try:
                    page.goto(target_url, timeout=timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(500)

                    form_elements = _sync_collect_form_elements(page)
                    inputs = form_elements.get("inputs", [])
                    buttons = form_elements.get("buttons", [])

                    filled_count = 0

                    if user or pwd:
                        if user:
                            matched = _match_field("username", inputs)
                            if matched:
                                ok = _sync_fill_field_by_info(page, matched, user)
                                if ok:
                                    filled_count += 1
                        if pwd:
                            matched = _match_field("password", inputs)
                            if matched:
                                ok = _sync_fill_field_by_info(page, matched, pwd)
                                if ok:
                                    filled_count += 1

                    if fdata:
                        for idx_str, value in fdata.items():
                            idx = int(idx_str)
                            if idx < len(inputs):
                                ok = _sync_fill_field_by_info(page, inputs[idx], str(value))
                                if ok:
                                    filled_count += 1

                    if auto_sub or btn_idx is not None:
                        if btn_idx is not None and btn_idx < len(buttons):
                            _sync_click_submit_button(page, [buttons[btn_idx]])
                        else:
                            _sync_click_submit_button(page, buttons)
                        page.wait_for_timeout(2000)

                    return {
                        "url": page.url,
                        "title": page.title(),
                        "fields_filled": filled_count,
                        "submitted": auto_sub or btn_idx is not None,
                        **_sync_take_screenshot(page),
                        "message": f"成功填写 {filled_count} 个字段",
                    }
                finally:
                    page.close()

            result = await asyncio.to_thread(
                manager.execute, _fill_form, url, form_data, username, password, click_button_index, auto_submit, timeout
            )
            return ToolResult(success=True, data=result)

        except Exception as exc:
            logger.bind(component="web").error("fill_webform failed: {}", exc)
            return ToolResult(success=False, error=f"填写表单失败: {exc}")


@register_tool(ToolMetadata(
    name="extract_webpage_text",
    description=(
        "提取网页的文本内容，用于阅读网页信息、抓取数据。"
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "要提取文本的网页 URL",
        },
        "selector": {
            "type": "string",
            "description": "CSS 选择器（可选），如 '.content'、'#table'、'table'",
        },
        "timeout": {
            "type": "integer",
            "description": "超时时间（毫秒），默认 30000",
        },
    },
))
class ExtractWebpageTextTool(BaseTool):
    """提取网页文本内容。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "").strip()
        selector = kwargs.get("selector", "").strip()
        timeout = int(kwargs.get("timeout", 30000))

        if not url:
            return ToolResult(success=False, error="缺少 url 参数")

        try:
            manager = await _get_sync_manager()

            def _extract(browser, target_url, sel, timeout_ms):
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                try:
                    page.goto(target_url, timeout=timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)

                    if sel:
                        content = page.evaluate(f"""() => {{
                            const els = document.querySelectorAll('{sel}');
                            const results = [];
                            els.forEach((el, i) => {{
                                results.push({{
                                    index: i,
                                    tag: el.tagName.toLowerCase(),
                                    text: el.textContent.trim().substring(0, 3000),
                                }});
                            }});
                            return results;
                        }}""")
                    else:
                        content = page.evaluate("""() => {
                            const main = document.querySelector('main, article, .content, #content, body');
                            if (main) {
                                return [{
                                    index: 0,
                                    tag: main.tagName.toLowerCase(),
                                    text: main.textContent.replace(/\\s+/g, ' ').trim().substring(0, 8000),
                                }];
                            }
                            return [{
                                index: 0,
                                tag: 'body',
                                text: document.body.textContent.replace(/\\s+/g, ' ').trim().substring(0, 8000),
                            }];
                        }""")

                    return {
                        "url": page.url,
                        "title": page.title(),
                        "content": content,
                        "count": len(content),
                    }
                finally:
                    page.close()

            result = await asyncio.to_thread(manager.execute, _extract, url, selector, timeout)
            return ToolResult(success=True, data=result)

        except Exception as exc:
            logger.bind(component="web").error("extract_webpage_text failed: {}", exc)
            return ToolResult(success=False, error=f"提取网页文本失败: {exc}")


__all__ = [
    "BrowseWebpageTool",
    "SmartFillFormTool",
    "FillWebformTool",
    "ExtractWebpageTextTool",
]