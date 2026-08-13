# OilChem Agent 项目状态报告 (v0.16.2)

> 更新：2026-08-13
> 基于全部源码逐文件阅读，不含推测。v0.16.2 变更：移除硬编码本地路径、版本号全量统一。

---

## 一、项目概述

**定位**：面向石油化工/化学实验室的 AI 助手，连接「人-硬件-软件-网页」的中间层。

**技术栈**：Python 3.12 + FastAPI + Pydantic v2 | React 18 + TypeScript + Vite | SQLite (aiosqlite) + SQLAlchemy | Loguru | Playwright (同步 API)

**代码规模**：后端 ~20 模块 / ~3000 行 Python，前端 9 组件 / ~1500 行 TSX，测试 2 个 smoke test

---

## 二、架构概览

```
前端 React SPA ──HTTP/SSE/WS──▶ FastAPI (main.py:123)
                                    │
    ┌─────────┬─────────┬────────────┼────────────┬──────────┐
    ▼         ▼         ▼            ▼            ▼          ▼
  system   health    /api/v1     lifespan      CORS       docs
                      router    (DB init +    (全开)    (/docs
                       │       FileWatcher)            /redoc)
    ┌────┬────┬────┬───┼───┬────┬────┐
    ▼    ▼    ▼    ▼   ▼   ▼    ▼    ▼
  chat  llm  web  files db hardware mcp(未接入)

Agent 内部管线:
  AgentManager → Planner(LLM输出JSON计划) → Executor(逐步执行工具) → Memory(内存存储)
                     │                            │
                 LLMClient                    ToolManager
                (重试+退避)                (@register_tool 装饰器)
                     │                            │
              OpenAIProvider              19个已注册工具
              OllamaProvider
```

---

## 三、逐模块状态清单

### 3.1 核心基础设施

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| FastAPI 应用 | `main.py` | ✅ 正常 | 启动/bootstrap/CORS/lifespan 完整 |
| 配置系统 | `core/config.py` | ✅ 正常 | Pydantic Settings，从 `.env` 读，`lru_cache` 单例 |
| 日志 | `core/logger.py` | ✅ 正常 | Loguru，stderr + `logs/app.log` 文件输出（10MB 轮转，14 天保留） |
| 常量 | `core/constants.py` | ✅ 正常 | v0.15.1 |
| 安全模块 | `core/security.py` | 🔌 空壳 | 仅含 docstring，无任何实现 |

### 3.2 LLM 层

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| 数据模型 | `llm/schemas.py` | ✅ 正常 | `ChatMessage`、`ChatCompletionRequest/Response`、`StreamChunk`、`ProviderConfig` |
| Provider 抽象 | `llm/provider.py` | ✅ 正常 | `BaseProvider` + `@register_provider` 装饰器，`get_provider()` 工厂 |
| OpenAI Provider | `llm/provider.py` | ✅ 正常 | SSE `data: ` 行解析，`/chat/completions` 路径 |
| Ollama Provider | `llm/provider.py` | ✅ 正常 | NDJSON 逐行解析，`/api/chat` 路径，字段名适配 (`prompt_eval_count`/`eval_count`) |
| LLM Client | `llm/client.py` | ✅ 正常 | 指数退避重试 (1s/2s/4s)，`from_settings()` 工厂，`test_connection()` |
| **限制** | - | ⚠️ | 不支持 function calling 的 `tools` 参数——工具调用靠 prompt engineering 让 LLM 输出 JSON |

### 3.3 工具系统

#### 3.3.1 工具框架

| 组件 | 文件 | 状态 |
|---|---|---|
| `BaseTool` 抽象基类 | `tools/base.py` | ✅ — `metadata` 类属性 + `async execute(**kwargs) -> ToolResult` |
| `@register_tool` 装饰器 | `tools/registry.py` | ✅ — 全局字典注册，按名查找 |
| `ToolManager` | `tools/manager.py` | ✅ — `execute(name, **kwargs)` + `list_available_tools()` |

#### 3.3.2 文件工具 (5个)

| 工具 | 状态 | 说明 |
|---|---|---|
| `read_file` | ✅ | 文本/二进制判定，行号范围，UTF-8，路径白名单检查 |
| `write_file` | ✅ | 覆盖写入，自动创建父目录 |
| `append_file` | ✅ | 追加模式，自动补换行 |
| `list_files` | ✅ | 支持 recursive + glob pattern |
| `delete_file` | ✅ | 仅文件不删目录（安全限制） |

#### 3.3.3 Office 工具 (6个)

| 工具 | 状态 | 依赖 |
|---|---|---|
| `read_excel` | 🔧 代码完整 | openpyxl，支持 sheet_name/index/header_row/max_rows |
| `write_excel` | 🔧 代码完整 | openpyxl，支持 append 模式 |
| `read_word` | 🔧 代码完整 | python-docx，提取段落+表格+标题 |
| `write_word` | 🔧 代码完整 | python-docx，段落+表格+Heading |
| `read_ppt` | 🔧 代码完整 | python-pptx，提取文本+表格+备注 |
| `write_ppt` | 🔧 代码完整 | python-pptx，布局选择简陋 (仅 title/blank/content) |

#### 3.3.4 网页工具 (4个) — 项目技术含量最高模块

| 工具 | 状态 | 说明 |
|---|---|---|
| `browse_webpage` | ✅ 已验证 | 打开网页→标题+文本+表单元素+截图(base64) |
| `smart_fill_form` | ✅ 已验证 | 6层字段匹配（name/id/placeholder/label/包含/关键词）+ 提交按钮检测 |
| `fill_webform` | 🔧 已实现 | 按索引精确填表，兼容模式 |
| `extract_webpage_text` | 🔧 已实现 | 支持 CSS selector，main/article/content 自动检测 |

**Playwright 架构（关键设计）**：`_SyncBrowserManager` — Actor 模式，专用后台线程 + `queue.Queue` 任务队列。解决了 Windows 下 `ProactorEventLoop` + greenlet 的 `Cannot switch to a different thread` 问题。支持多策略浏览器查找（Playwright 默认 → 系统 Chrome → 系统 Edge → 自定义路径）。

#### 3.3.5 图表工具 (1个)

| 工具 | 状态 | 说明 |
|---|---|---|
| `plot_chart` | 🔧 已实现 | matplotlib Agg backend，支持 plot/bar/scatter/hist，多系列+图例，中文 `Microsoft YaHei` 字体，base64 PNG 输出 |

#### 3.3.6 硬件工具 (3个) — 2 个 Mock + 1 个真实 ORM

| 工具 | 状态 | 说明 |
|---|---|---|
| `read_hardware` | ⚠️ Mock | 5 个硬编码假设备，`_refresh_metrics()` 加 ±2% 随机漂移 |
| `send_hardware_command` | ⚠️ Mock | 假闭环：`requests.post()` 回调自己 API 端点 |
| `query_hardware_history` | ✅ 可用 | v0.16.0 新增。查询 `DeviceTelemetryHistory` 表，配合后台采集器实现持久化趋势分析 |

### 3.4 Agent 系统

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| AgentManager | `agent/manager.py` | ✅ | 协调 Planner/Executor/Memory/LLM，`chat()` + `chat_stream()` |
| Planner | `agent/planner/planner.py` | 🔧 | LLM 输出 JSON 计划，三层 JSON 提取容错，**强依赖 LLM 质量** |
| Executor | `agent/executor.py` | 🔧 | 逐步执行+步骤间上下文传递 (`{step_N_result}` 模板) + 失败续跑判断 |
| MemoryManager | `agent/memory/memory.py` | 🔧 | 纯内存（重启丢失），超 50 条截断压缩（非 LLM 摘要，仅拼接），朴素子串搜索 |
| Prompts | `agent/prompts/prompts.py` | 🔧 | 三层提示词：默认+石油化工领域+实验室自动化，含 `smart_fill_form` 使用示例 |

**Planner 的关键风险**：工具调用靠 prompt engineering 让 LLM 输出 JSON，不用 function calling。`_extract_json_object()` 做了三层容错（直接 parse → 代码块提取 → 花括号匹配），但容错失败时降级为纯 LLM 步骤，用户无感知。用 `qwen2.5` 级别的小模型跑规划，JSON 合法率和步骤合理性均未验证。

### 3.5 API 端点

| 端点 | 方法 | 状态 | 备注 |
|---|---|---|---|
| `/` | GET | ✅ | 返回 name/version/status |
| `/health` | GET | ✅ | `{"status":"ok"}` |
| `/api/v1/chat` | POST | ✅ | 完整 Agent 管线 |
| `/api/v1/chat/stream` | POST | 🔧 | SSE: planning→tools→chart→thinking→chunk→done→error |
| `/api/v1/chat/sessions` | GET | 🔧 | 列出会话 |
| `/api/v1/chat/sessions/{id}` | GET/DELETE | 🔧 | 获取/删除会话 |
| `/api/v1/llm/test` | GET | 🔧 | 连通性测试 |
| `/api/v1/llm/info` | GET | 🔧 | 返回 provider/model/url/timeout |
| `/api/v1/web/browse` | POST | ✅ | 已验证 |
| `/api/v1/web/smart-fill` | POST | ✅ | 已验证 |
| `/api/v1/web/fill-form` | POST | 🔧 | |
| `/api/v1/web/extract-text` | POST | 🔧 | |
| `/api/v1/files/preview` | POST | 🔧 | 含 Office 文件预览 |
| `/api/v1/files/read|write|append|list|delete` | POST | 🔧 | 文件 CRUD |
| `/api/v1/files/tools` | GET | 🔧 | 列出文件工具 |
| `/api/v1/files/watch/start|stop` | POST | 🔧 | 文件监听开关 |
| `/api/v1/ws/files/events` | WS | 🔧 | 文件变化推送+心跳 |
| `/api/v1/hardware/*` | GET/POST | ⚠️ Mock | 3 个端点全量假数据 |
| `/api/v1/db/*` | GET/POST/DELETE | ✅ 已接入 ORM | 5 个端点，`AsyncSession` + `select()` 真实查询 |

### 3.6 数据库

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| Base 类 | `database/base.py` | ✅ | `DeclarativeBase` |
| 会话管理 | `database/session.py` | ✅ | 异步引擎+sessionmaker+FastAPI 依赖注入，含种子数据自动填充 |
| ORM 模型 | `models/tables.py` | ✅ | User/Session/Message/ToolAudit/Knowledge + 业务表 Experiment/Sample/Device |
| Alembic | `alembic/` | ✅ | 配置+初始迁移脚本 `001_initial_tables.py` |
| DB API 端点 | `api/v1/endpoints/db.py` | ✅ 已接入 ORM | v0.15.0 使用 `get_db()` 依赖注入，`AsyncSession` + `select()` 查询 |
| init_db() | `database/session.py:64` | ✅ | 优先 Alembic → 回退 create_all → 种子数据填充，启动时自动调用 |

### 3.7 前端

| 组件 | 状态 | 说明 |
|---|---|---|
| `App.tsx` | 🔧 | 5 Tab 导航 (对话/文件/硬件/数据/网页填表) |
| `ChatWindow.tsx` | 🔧 | SSE 流式消费，7 种事件类型处理 |
| `Sidebar.tsx` | 🔧 | 会话列表，新建/选择/删除 |
| `FileBrowser.tsx` | 🔧 | 文件树浏览+预览 |
| `HardwarePanel.tsx` | 🔧 | 设备卡片+指标展示 |
| `DatabasePanel.tsx` | 🔧 | 表选择+数据列表+SQL 查询框 |
| `WebFormPanel.tsx` | 🔧 | URL+字段映射+截图展示 |
| `MessageList.tsx` / `Message.tsx` / `MessageInput.tsx` | 🔧 | 对话 UI 组件 |
| `api.ts` | 🔧 | 完整 API 封装（chat/files/web/sessions/llm/health） |
| **整体** | ✅ | 组件完整，`npm run build` 通过（v0.15.1 首次） |

### 3.8 辅助模块

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| 输入护栏 | `guardrails/input_guard.py` | ✅ 已接入 | v0.15.0 接入 `chat()` 和 `chat_stream()`，注入检测 + 敏感信息脱敏 |
| 输出护栏 | `guardrails/output_guard.py` | ✅ 已接入 | v0.15.0 接入，输出过滤 + 敏感信息泄露防护 |
| 权限管理 | `guardrails/permission.py` | 🔧 已写未接 | RBAC 模型完整，尚未接入 API 端点 |
| MCP 客户端 | `mcp/client.py` | 🔧 已写未接 | MCPClient + MCPManager 完整，**从未被 Agent 引用** |
| 文件监听 | `services/file_watcher.py` | 🔧 | watchdog PollingObserver + 防抖合并 + WebSocket 分发 |
| 遥测采集 | `services/hardware_collector.py` | ✅ | v0.16.0 新增。后台 10s 轮询写入 SQLite，每次采集后自动清理过期数据（默认保留 24h） |
| 一键启动 | `start.py` | ✅ | 400行：环境检查→venv→pip→npm→后台启动→浏览器打开 |

### 3.9 遥测数据自动清理机制

硬件遥测数据写入 SQLite 后会无限增长，为避免表膨胀，采集器内置自动清理：

| 项 | 值 |
|---|---|
| 触发时机 | **每次采集循环后**（每 10 秒） |
| 保留窗口 | 默认 **24 小时**（`HARDWARE_HISTORY_RETENTION_MINUTES=1440`） |
| 清理逻辑 | 删除 `timestamp < now - 保留窗口` 的所有记录 |
| 已验证 | 3 天前记录被删、1 小时前记录保留 ✅ |

调整保留时长：改 `backend/.env` 中 `HARDWARE_HISTORY_RETENTION_MINUTES` 即可（如 10080 = 7 天），无需改代码。

> 注：清理日志级别为 debug，当前 `LOG_LEVEL=INFO` 下不可见；将 `LOG_LEVEL` 改为 `DEBUG` 可看到 "Cleaned N stale telemetry records"。

---

## 四、已注册工具总览 (19个)

| 分类 | 工具 | 状态 |
|---|---|---|
| 文件 | `read_file` `write_file` `append_file` `list_files` `delete_file` | 🔧 |
| Office | `read_excel` `write_excel` `read_word` `write_word` `read_ppt` `write_ppt` | 🔧 |
| 网页 | `browse_webpage` `smart_fill_form` `fill_webform` `extract_webpage_text` | ✅~🔧 |
| 图表 | `plot_chart` | 🔧 |
| 硬件 | `read_hardware` `send_hardware_command` `query_hardware_history` | ⚠️~✅ |

---

## 五、已知问题与限制

### 5.1 架构缺陷
1. **全局单例泛滥**：`get_agent()`、`get_file_watcher()`、`settings` 模块级实例，无 DI 容器
2. **MemoryManager 纯内存**：进程重启全部丢失
3. **无 function calling**：工具调用靠 LLM 输出 JSON，小模型成功率堪忧
4. **测试严重不足**：仅 2 个 smoke test，无集成测试

### 5.2 未接入的代码
1. **权限管理**：`guardrails/permission.py` 的 RBAC 模型完整，未接入 API 端点
2. **MCP**：`mcp/client.py` 框架完整但从未在 Agent 管线中引用，无任何 MCP Server 配置
3. **用户认证**：`AUTH_ENABLED=false`，`security.py` 空壳，无 login 端点

### 5.3 硬件的假闭环
`send_hardware_command` → `requests.post(127.0.0.1:8000/api/v1/hardware/devices/{id}/command)` → 端点返回 `{"status":"queued"}` → 工具返回 `success=True`。从工具到端点到响应，没有任何真实硬件通信。

### 5.4 Playwright 限制
- Headless 模式，无反反爬虫措施
- 无 iframe 处理，无多标签页，无文件下载
- 不支持验证码识别
- 未持久化浏览器状态（每次新会话）

### 5.5 其他
- 无 Docker/容器化
- `start.py` 使用 `shell=True`（安全风险），stdout/stderr 丢弃到 `DEVNULL`
- 无限流、无并发控制

---

## 六、一行总结

**骨骼完整、核心链路可用（Guardrails + ORM + Playwright + 硬件遥测采集）的原型项目。** DB 端点已从 Mock 转为真实 ORM 持久化，Guardrails 已接线，硬件后台遥测采集器和历史查询工具已就绪。短期缺的是集成测试，长期需要从零建设真实硬件网关。

---

## 七、版本统一确认

| 位置 | 版本号 |
|---|---|
| `backend/pyproject.toml` | 0.16.2 |
| `backend/.env` (APP_VERSION) | 0.16.2 |
| `backend/.env.example` | 0.16.2 |
| `backend/app/core/config.py` (default) | 0.16.2 |
| `backend/app/core/constants.py` | 0.16.2 |
| `frontend/package.json` | 0.16.2 |
| `frontend/src/App.tsx` | v0.16.2 |
| `frontend/src/components/Sidebar.tsx` | v0.16.2 |
| `docs/api.md` | 0.16.2 |

## 八、v0.16.2 变更记录

1. **移除 3 处硬编码本地路径**：`FileBrowser.tsx` 默认目录改为空字符串，后端 `_resolve_path()` 对空路径回退到项目根目录（`Path(__file__).parents[4]` 代码相对定位），行为与原默认一致；Planner 提示词示例路径改为通用写法；`file_access_scope.md` 改为描述 `FILE_ALLOWED_PATHS` 配置
2. **版本号全量统一**：`.env.example`/CLAUDE.md/DEVELOPMENT.md/README.md 同步到 0.16.2，与代码 9 处版本号一致

## 九、v0.16.1 变更记录

1. **系统提示词新增「硬件设备使用指南」**：列出 5 台设备及指标，明确 `read_hardware`(实时) / `query_hardware_history`(历史) 分工，给出画趋势图标准步骤
2. **工具描述优化**：两个硬件工具 description 各自强调实时/历史定位，device_id 参数补充中文设备名
3. **效果**：Agent 能正确区分"实时读数"（用 read_hardware）和"历史趋势"（用 query_hardware_history），消除割裂感

## 九、v0.16.0 变更记录

1. **硬件遥测采集服务**：`HardwareCollectorService` 后台 10s 轮询写入 `DeviceTelemetryHistory` OLTP 表，含过期清理
2. **Agent 工具 `query_hardware_history`**：第 19 个已注册工具，按设备/指标/时间范围查询历史，降采样 + 直接喂 `plot_chart`
3. **Executor 上下文引用增强**：`{step_N_result.字段名}` 点路径提取，保留原始类型
4. **`plot_chart` 缩进 bug 修复**：校验代码吞掉了图表生成逻辑
5. **Planner prompt 优化**：教 LLM 用模板引用替代自然语言占位符

## 九、v0.15.1 变更记录

1. **前端全局错误提示**：新增 `ErrorToast.tsx`，通过 `notifyError()` 派发 CustomEvent 在页面顶部显示红色提示，替换 `alert()` 弹窗
2. **首次通过生产构建**：`npm run build` 首次成功，修复 `FileBrowser.tsx` 隐式 `any` 类型和 `Message.tsx` 未使用变量

## 十、v0.15.0 变更记录

1. **Guardrails 接入**：`InputGuardrail` 接入 `POST /chat` 和 `POST /chat/stream`（注入检测 + 脱敏）；`OutputGuardrail` 接入 `POST /chat`（内容过滤），`POST /chat/stream` 在完成时做审计日志
2. **DB 端点接入 ORM**：新增 `Experiment`/`Sample`/`Device` ORM 模型；`db.py` 从内存列表重写为 `AsyncSession` + `select()` 真实查询；`init_db()` 增加种子数据自动填充（幂等）
3. **版本号全量统一**：8 处版本号统一为 0.15.0
4. **日志增强**：chat 端点增加护栏阻断/成功/异常的 Loguru 日志条目；DB 端点增加 CRUD 操作日志
