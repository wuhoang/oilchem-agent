# OilChem Agent 项目状态报告 (v1.3.1)

> 更新：2026-08-16
> v1.3.0 变更：用户认证（JWT 登录 + 全量鉴权开关）、RBAC 接入（操作员/审核人/管理员）、审核人联动账号、前端登录页、认证测试 7 例。

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
    ┌────┬────┬────┬───┼───┬────┬────┬─────────┐
    ▼    ▼    ▼    ▼   ▼   ▼    ▼    ▼         ▼
  chat  llm  web  files db hardware mcp experiments

Agent 内部管线:
  AgentManager ─ function calling ─▶ ToolManager ─▶ 25个已注册工具
         │               │            (@register_tool 装饰器)
      Memory          LLMClient
   (纯内存会话)      (重试+退避)
                         │
                 OpenAIProvider / OllamaProvider
  （旧 Planner→Executor 链路保留，未挂主链路）
```

---

## 三、逐模块状态清单

### 3.1 核心基础设施

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| FastAPI 应用 | `main.py` | ✅ 正常 | 启动/bootstrap/CORS/lifespan 完整 |
| 配置系统 | `core/config.py` | ✅ 正常 | Pydantic Settings，从 `.env` 读，`lru_cache` 单例 |
| 日志 | `core/logger.py` | ✅ 正常 | Loguru，stderr + `logs/app.log` 文件输出（10MB 轮转，14 天保留） |
| 常量 | `core/constants.py` | ✅ 正常 | APP_NAME/APP_VERSION 常量定义 |
| 安全模块 | `core/security.py` | ✅ v1.3.0 实装 | PBKDF2 密码哈希 + PyJWT HS256 签发/验签，密钥/过期时间走 Settings |

### 3.2 LLM 层

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| 数据模型 | `llm/schemas.py` | ✅ 正常 | `ChatMessage`、`ChatCompletionRequest/Response`、`StreamChunk`、`ProviderConfig` |
| Provider 抽象 | `llm/provider.py` | ✅ 正常 | `BaseProvider` + `@register_provider` 装饰器，`get_provider()` 工厂 |
| OpenAI Provider | `llm/provider.py` | ✅ 正常 | SSE `data: ` 行解析，`/chat/completions` 路径 |
| Ollama Provider | `llm/provider.py` | ✅ 正常 | NDJSON 逐行解析，`/api/chat` 路径，字段名适配 (`prompt_eval_count`/`eval_count`) |
| LLM Client | `llm/client.py` | ✅ 正常 | 指数退避重试 (1s/2s/4s)，`from_settings()` 工厂，`test_connection()` |
| **能力** | - | ✅ | 已支持 function calling：`LLMClient.chat(tools=...)` 透传 OpenAI tools 协议，provider 将 tools 写入请求 payload |

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

#### 3.3.6 硬件工具 (3个) — 统一设备源，Mock 驱动

| 工具 | 状态 | 说明 |
|---|---|---|
| `read_hardware` | ✅ 统一源 | v1.1.0 起从 DriverRegistry 读 6 台油化仿真设备（HTHP/Rheo/Thick），设备实时遥测受编排引擎控制 |
| `send_hardware_command` | ✅ 统一源 | v1.1.0 起走 DriverRegistry 下发指令（`driver.send_command`），不再 requests 回调自己 API |
| `query_hardware_history` | ✅ 可用 | 查询 `DeviceTelemetryHistory` 表，后台采集器从 DriverRegistry 读遥测，实现持久化趋势分析 |

#### 3.3.7 实验域工具 (6个) — v1.0.0/v1.1.0 新增

| 工具 | 状态 | 说明 |
|---|---|---|
| `list_protocols` | ✅ | 列出实验方案 |
| `create_experiment` | ✅ | 创建实验（选方案+操作员+样品） |
| `start_experiment` | ✅ | 启动实验（触发编排引擎） |
| `query_experiment_progress` | ✅ | 查询实验进度 |
| `query_experiment_result` | ✅ | 查询实验结果/测量数据 |
| `generate_experiment_report` | ✅ | 生成实验报告文件（Word+Excel），单轮完成 |

### 3.4 Agent 系统

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| AgentManager | `agent/manager.py` | ✅ | v0.17.0 起主链路为原生 function calling：`chat_with_tools()` + `chat_stream_with_tools()`，模型输出结构化 tool_calls，工具结果 role="tool" 回传 |
| Planner | `agent/planner/planner.py` | 🔧 保留 | 旧的"手写 JSON 计划"链路，v0.17.0 起不再作为主入口，保留供降级/测试 |
| Executor | `agent/executor.py` | 🔧 保留 | 同上，`{step_N_result}` 模板传数据机制已退役（function calling 天然保留类型） |
| MemoryManager | `agent/memory/memory.py` | 🔧 | 纯内存（重启丢失），工具往返不写入 memory（避免污染多轮对话） |
| Prompts | `agent/prompts/prompts.py` | 🔧 | 三层提示词：默认+石油化工领域+实验室自动化 |

**function calling 主链路（v0.17.0）**：`ToolManager.list_tools_schema()` 把 25 个工具转成 OpenAI tools 协议，模型直接输出结构化 `tool_calls`（参数由协议保证合法 JSON），工具结果以 `role="tool"` 消息回传，模型自主决定继续/重试/给最终回答。含 `max_iterations=8` 防死循环。旧的 Planner（手写 JSON 计划）链路已从主调用方移除，文件保留待稳定后清理。

### 3.5 API 端点

| 端点 | 方法 | 状态 | 备注 |
|---|---|---|---|
| `/` | GET | ✅ | 返回 name/version/status |
| `/health` | GET | ✅ | `{"status":"ok"}` |
| `/api/v1/chat` | POST | ✅ | 完整 Agent 管线 |
| `/api/v1/chat/stream` | POST | 🔧 | SSE: thinking→tools→chart→chunk→done→error |
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
| `/api/v1/hardware/*` | GET/POST | ✅ 统一源 | 从 DriverRegistry 读 6 台油化仿真设备，BUSY 状态，send_command 走统一源 |
| `/api/v1/db/*` | GET/POST/DELETE | ✅ 已接入 ORM | 5 个端点，`AsyncSession` + `select()` 真实查询 |
| `/api/v1/protocols` | GET | ✅ | 方案库列表/详情 |
| `/api/v1/experiments` | GET/POST | ✅ | 实验列表/创建 |
| `/api/v1/experiments/{id}` | GET | ✅ | 实验详情（含步骤+追溯链+报告路径） |
| `/api/v1/experiments/{id}/start` | POST | ✅ | 启动实验 |
| `/api/v1/experiments/{id}/progress` | GET | ✅ | 进度快照 |
| `/api/v1/experiments/{id}/measurements` | GET | ✅ | 测量数据（时间序列） |
| `/api/v1/experiments/{id}/report` | GET | ✅ | 报告文件清单（Word+Excel） |
| `/api/v1/experiments/{id}/retry-step\|skip-step\|abort` | POST | ✅ | 异常介入 |
| `/api/v1/experiments/events` | GET | ✅ | SSE 实验事件流 |
| `/api/v1/experimenters` | GET | ✅ | 实验员列表 |
| `/api/v1/dashboard` | GET | ✅ | 看板聚合 |

### 3.6 数据库

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| Base 类 | `database/base.py` | ✅ | `DeclarativeBase` |
| 会话管理 | `database/session.py` | ✅ | 异步引擎+sessionmaker+FastAPI 依赖注入，含种子数据自动填充 |
| ORM 模型 | `models/tables.py` | ✅ | 16 张表：User/Session/Message/ToolAudit/Knowledge + 业务表 Experiment/Sample/Device/DeviceTelemetryHistory/ExperimentAudit/Experimenter/Protocol/ProtocolStep/Material/ExperimentStep/Measurement |
| Alembic | `alembic/` | ✅ | 4 个迁移脚本：001_initial_tables → 002_device_telemetry_history → 003_experiment_domain_tables → 004_experiment_report_and_types |
| DB API 端点 | `api/v1/endpoints/db.py` | ✅ 已接入 ORM | v0.15.0 使用 `get_db()` 依赖注入，`AsyncSession` + `select()` 查询 |
| init_db() | `database/session.py:64` | ✅ | 优先 Alembic → 回退 create_all → 种子数据填充，启动时自动调用 |

### 3.7 前端

| 组件 | 状态 | 说明 |
|---|---|---|
| `App.tsx` | 🔧 | 6 Tab 导航 (对话/实验中心/文件/硬件/数据/网页填表) |
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
| 权限管理 | `guardrails/permission.py` | ✅ v1.3.0 接入 | RBAC 角色扩展（admin/operator/reviewer），`require_role()` 依赖接入实验审核端点 |
| 认证 | `api/v1/endpoints/auth.py` + `api/deps.py` | ✅ v1.3.0 | JWT 登录（POST /auth/login）+ /auth/me；`AUTH_ENABLED=true` 全量鉴权；SSE 走 `?token=` |
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

## 四、已注册工具总览 (25个)

| 分类 | 工具 | 状态 |
|---|---|---|
| 文件 | `read_file` `write_file` `append_file` `list_files` `delete_file` | 🔧 |
| Office | `read_excel` `write_excel` `read_word` `write_word` `read_ppt` `write_ppt` | 🔧 |
| 网页 | `browse_webpage` `smart_fill_form` `fill_webform` `extract_webpage_text` | ✅~🔧 |
| 图表 | `plot_chart` | 🔧 |
| 硬件 | `read_hardware` `send_hardware_command` `query_hardware_history` | ⚠️~✅ |
| 实验 | `list_protocols` `create_experiment` `start_experiment` `query_experiment_progress` `query_experiment_result` `generate_experiment_report` | 🔧 |

---

## 五、已知问题与限制

### 5.1 架构缺陷
1. **全局单例泛滥**：`get_agent()`、`get_file_watcher()`、`settings` 模块级实例，无 DI 容器
2. **MemoryManager 纯内存**：进程重启全部丢失
3. **旧 Planner→Executor 链路未清理**：与 function calling 主链路并存，代码重复、维护成本高
4. **测试严重不足**：仅 2 个 smoke test，无集成测试

### 5.2 未接入的代码
1. **MCP**：`mcp/client.py` 框架完整但从未在 Agent 管线中引用，无任何 MCP Server 配置
2. ~~**权限管理**~~：已接入（v1.3.0，实验审核端点角色校验 + 审核人列表查账号）
3. ~~**用户认证**~~：已接入（v1.3.0，JWT 登录 + `AUTH_ENABLED` 开关 + 前端登录页）；`AUTH_ENABLED=false` 为默认值，本地演示仍免登录

### 5.3 硬件仍为模拟（无真实通信）
`send_hardware_command` → `DriverRegistry.get(device_id)` 取 `MockDriver` → `driver.send_command()` 返回 `{"status":"queued","message":"...（模拟）"}` → 工具返回 `success=True`。底层是 MockDriver 模拟器，没有任何真实 RS232/USB/GPIB 通信。

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
| `backend/pyproject.toml` | 1.3.1 |
| `backend/.env` (APP_VERSION) | 1.3.1 |
| `backend/.env.example` | 1.3.1 |
| `backend/app/core/config.py` (default) | 1.3.1 |
| `backend/app/core/constants.py` | 1.3.1 |
| `frontend/package.json` | 1.3.1 |
| `frontend/package-lock.json` | 1.3.1 |
| `frontend/src/App.tsx` | v1.3.1 |
| `frontend/src/components/Sidebar.tsx` | v1.3.1 |
| `docs/api.md` | 1.3.1 |

## 八、v1.3.0 变更记录

1. **用户认证（JWT）**：`security.py` 实装（PBKDF2 密码哈希 + PyJWT HS256）；`POST /auth/login` + `GET /auth/me`；`AUTH_ENABLED=true` 时全量鉴权（auth/SSE 路由单独挂载豁免）
2. **RBAC 接入**：`require_role()` 依赖；实验审核端点限 reviewer/admin；`permission.py` 角色扩展为 admin/operator/reviewer
3. **审核人联动账号**：`GET /reviewers` 改为查 users 表 reviewer/admin 角色；approve/reject 写入账号 ID
4. **SSE 鉴权**：`/experiments/events` 走 `?token=` query 参数
5. **前端登录页**：LoginPage + api.ts 统一带 token + 401 跳登录 + 顶部用户/角色显示 + 退出
6. **认证测试**：`tests/test_auth.py` 7 用例
7. **修复**：本地库 `experiments.reviewed_by_id` 缺列导致数据库初始化失败，已补列
8. **版本号 1.2.0 → 1.3.0**

## 九、v1.2.0 变更记录

1. **实验审核**：状态机新增「待审核」「已驳回」；实验跑完生成报告后进入「待审核」，`POST /experiments/{id}/approve`（通过→已完成）/`reject`（驳回→已驳回）；`Experiment` 加 `reviewed_by`/`reviewed_by_id`/`reviewed_at`/`review_comment` 字段（Alembic 005）
2. **审核人选择**：新增 `GET /reviewers` 端点（当前返回实验员，将来账号管理完善后改查有审核权限的账号）；前端「待审核」状态显示审核人下拉（默认当前操作员=可自审，可选他人），替代写死操作员本人
3. **待审核可查看报告**：报告在进入「待审核」时已生成，前端「待审核」状态也显示「生成/下载报告」按钮
4. **版本号 1.1.0 → 1.2.0**

## 九、v1.1.0 变更记录

1. **实验报告自动生成**：新增 `generate_experiment_report` 工具（第 25 个工具）+ `services/report_generator.py` + `GET /experiments/{id}/report` 端点
2. **实验追溯视图**：`ExperimentAudit` 审计链路补全，实验过程可追溯
3. **油化仿真设备源统一**：`_register_devices()` 从 `hardware_info/hardware_simulation_data.json` 加载油化设备（高温高压失水仪/六速流变仪/稠化仪），统一注册到 DriverRegistry；`hardware.py` 端点、`devices` 表 seed 已统一为同一套设备 ID（已删除写死兜底）。注意：驱动仍是 MockDriver 模拟器，非真实 RS232/USB/GPIB 通信
4. **SSE 实时事件**：新增 `GET /experiments/events`，实验进度实时推送
5. **设备复位修复**
6. **工具数 24 → 25**，版本号 1.0.0 → 1.1.0

## 十、v1.0.0 变更记录

1. **实验域完整闭环（M1-M7）**：新增 6 表 + 扩 2 表 + Alembic 003；`DeviceDriver` 抽象 + `MockDriver` 剧本引擎 + `DriverRegistry`；`Orchestrator` 状态机 + 主循环 + 异常恢复；12 个实验域 REST 端点 + 5 个实验域 Agent 工具；`ExperimentAudit` 审计；前端「实验中心」Tab
2. **演示主场景**：HTHP 高温高压失水仪方案（升温→恒温→测漏失量，漏失量按 7 点曲线产出）
3. **工具数 19 → 24**，版本号跳跃至 1.0.0

## 十、v0.17.0 变更记录

1. **Agent 工具调用迁移到原生 function calling**：模型输出结构化 tool_calls，工具结果 role="tool" 回传，替代旧的"手写 JSON 计划"链路
2. **`ToolManager.list_tools_schema()` + `_normalize_schema()`**：统一规范化工具参数为标准 JSON Schema（修复 14 个工具扁平格式导致 400 的 bug）
3. **前端实时工具调用流**：`ToolCallInfo.step_id` → `call_index`，流式事件移除 planning
4. **防死循环**：`max_iterations=8`，工具往返不写 Memory，图片走 chart 事件不进 LLM 上下文

## 十一、v0.16.3 变更记录

1. **默认 LLM 修正为 DeepSeek**：`config.py` 默认值从 `ollama + qwen2.5` 改为 `openai + https://api.deepseek.com/v1 + deepseek-chat`（实际运行仍以 `.env` 为准）；CLAUDE.md、README、api.md 中 qwen2.5/Ollama 的误导性默认描述已清理，Ollama 仅保留为可选预留方案
2. **版本号统一到 0.16.3**：代码 8 处 + `.env.example`/CLAUDE.md/DEVELOPMENT.md 同步

## 十二、v0.16.2 变更记录

1. **移除 3 处硬编码本地路径**：`FileBrowser.tsx` 默认目录改为空字符串，后端 `_resolve_path()` 对空路径回退到项目根目录（`Path(__file__).parents[4]` 代码相对定位），行为与原默认一致；Planner 提示词示例路径改为通用写法；`file_access_scope.md` 改为描述 `FILE_ALLOWED_PATHS` 配置
2. **版本号全量统一**：`.env.example`/CLAUDE.md/DEVELOPMENT.md/README.md 同步到 0.16.2，与代码 9 处版本号一致

## 十三、v0.16.1 变更记录

1. **系统提示词新增「硬件设备使用指南」**：列出 5 台设备及指标，明确 `read_hardware`(实时) / `query_hardware_history`(历史) 分工，给出画趋势图标准步骤
2. **工具描述优化**：两个硬件工具 description 各自强调实时/历史定位，device_id 参数补充中文设备名
3. **效果**：Agent 能正确区分"实时读数"（用 read_hardware）和"历史趋势"（用 query_hardware_history），消除割裂感

## 十四、v0.16.0 变更记录

1. **硬件遥测采集服务**：`HardwareCollectorService` 后台 10s 轮询写入 `DeviceTelemetryHistory` OLTP 表，含过期清理
2. **Agent 工具 `query_hardware_history`**：第 19 个已注册工具，按设备/指标/时间范围查询历史，降采样 + 直接喂 `plot_chart`
3. **Executor 上下文引用增强**：`{step_N_result.字段名}` 点路径提取，保留原始类型
4. **`plot_chart` 缩进 bug 修复**：校验代码吞掉了图表生成逻辑
5. **Planner prompt 优化**：教 LLM 用模板引用替代自然语言占位符

## 十五、v0.15.1 变更记录

1. **前端全局错误提示**：新增 `ErrorToast.tsx`，通过 `notifyError()` 派发 CustomEvent 在页面顶部显示红色提示，替换 `alert()` 弹窗
2. **首次通过生产构建**：`npm run build` 首次成功，修复 `FileBrowser.tsx` 隐式 `any` 类型和 `Message.tsx` 未使用变量

## 十六、v0.15.0 变更记录

1. **Guardrails 接入**：`InputGuardrail` 接入 `POST /chat` 和 `POST /chat/stream`（注入检测 + 脱敏）；`OutputGuardrail` 接入 `POST /chat`（内容过滤），`POST /chat/stream` 在完成时做审计日志
2. **DB 端点接入 ORM**：新增 `Experiment`/`Sample`/`Device` ORM 模型；`db.py` 从内存列表重写为 `AsyncSession` + `select()` 真实查询；`init_db()` 增加种子数据自动填充（幂等）
3. **版本号全量统一**：8 处版本号统一为 0.15.0
4. **日志增强**：chat 端点增加护栏阻断/成功/异常的 Loguru 日志条目；DB 端点增加 CRUD 操作日志
