# Changelog

All notable changes to OilChem Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.16.3] - 2026-08-13

### Fixed

- **消除"项目用本地小模型 qwen2.5"的误导**：实际使用 DeepSeek（deepseek-chat），但 CLAUDE.md、README、api.md、PROJECT_STATUS.md 多处残留 qwen2.5/Ollama 描述，导致审查 Agent 误判
- `config.py` 默认值从 `ollama + qwen2.5` 改为 `openai + deepseek-chat`（实际运行仍以 `.env` 为准）
- CLAUDE.md 明确标注：实际 LLM 为 DeepSeek，Ollama 仅为预留 Provider

## [0.16.2] - 2026-08-13

### Fixed

- 移除 3 处硬编码本地路径：`FileBrowser.tsx` 文件浏览器默认目录改为空字符串，后端 `list_files` 等工具对空路径回退到项目根目录（代码相对定位，不写死本机路径）；Planner 系统提示词中的示例路径改为通用占位写法；`docs/file_access_scope.md` 改为描述 `FILE_ALLOWED_PATHS` 配置
- 版本号全量统一：`.env.example`、CLAUDE.md、DEVELOPMENT.md、README.md 从过期的 0.15.0/0.16.0 同步到 0.16.2

## [0.16.1] - 2026-08-10

### Changed

- 系统提示词新增「硬件设备使用指南」：列出 5 台设备及指标、明确 `read_hardware`(实时) 与 `query_hardware_history`(历史) 的职责分工、给出画趋势图的标准步骤
- `read_hardware` 工具描述优化：强调「实时快照」定位，指明历史查询请用 `query_hardware_history`
- `query_hardware_history` 工具描述优化：强调「历史趋势」定位，指明实时查询请用 `read_hardware`

### 效果

- Agent 现在能正确区分"实时读数"和"历史趋势"：
  - 问"现在温度多少" → 用 `read_hardware` 返回实时值
  - 问"过去30分钟趋势" → 用 `query_hardware_history` 返回时间序列并画图

## [0.16.0] - 2026-08-10

### Added

- 设备遥测历史采集服务：`HardwareCollectorService` 后台轮询采集硬件指标写入数据库（默认 10s 间隔），启动时自动运行
- ORM 模型 `DeviceTelemetryHistory` — 存储 device_id / metric_name / metric_value / unit / timestamp，含 Alembic 迁移 002
- Agent 工具 `query_hardware_history` (第 19 个已注册工具) — 按设备/指标/时间范围查询历史数据，支持降采样，返回结构化 JSON 可直接喂给 `plot_chart`
- Executor 上下文引用增强：支持 `{step_N_result.字段名}` 点路径提取，保留原始类型（list/float 等）
- 配置项 `HARDWARE_COLLECT_INTERVAL` (10s) 和 `HARDWARE_HISTORY_RETENTION_MINUTES` (1440min，自动清理保留窗口)

### Fixed

- `plot_chart` 缩进 bug：数据校验后生成代码被吞入 except 块成为死代码，导致 `NoneType` 异常
- `chart_tools.py` 新增 y_data 类型/数值校验，对字符串占位符给出明确错误提示
- Planner prompt 新增步骤间数据传递规则（教 LLM 写模板引用），f-string 花括号转义修复

### Changed

- `executor.py` 移除 `tool_args.update(step.tool_args)`（会覆盖上下文解析结果）
- `main.py` lifespan 统一管理硬件采集器的启停

## [0.15.1] - 2026-08-10

### Added

- 前端全局错误提示条 `ErrorToast.tsx`：通过 `notifyError()` 派发 CustomEvent，在页面顶部显示红色提示并自动消失
- 错误提示接入对话端点（SSE error 事件 + 请求失败）和数据管理面板（新增/编辑/删除失败），替换原有的 `alert()` 弹窗
- 首次跑通 `npm run build` 生产构建（此前从未构建过）

### Fixed

- 前端首次通过 TypeScript 严格检查：修复 `FileBrowser.tsx` 的隐式 `any` 类型（Word/PPT 预览组件）、`Message.tsx` 未使用变量
- `Message.tsx` 删除了未使用的 `ChartData` 导入和 `match` 变量

## [0.15.0] - 2026-08-10

### Added

- Guardrails 接入对话端点：`InputGuardrail` 接入 `POST /chat` 和 `POST /chat/stream`（Prompt 注入检测 + 敏感信息脱敏）；`OutputGuardrail` 接入 `POST /chat`（有害内容过滤），`POST /chat/stream` 完成时审计日志
- DB 端点接入 ORM：新增 `Experiment`/`Sample`/`Device` ORM 模型；`db.py` 从内存列表重写为 `AsyncSession` + `select()` 真实 SQLite 查询；`init_db()` 增加种子数据自动填充（幂等）
- 前端 `DatabasePanel.tsx` 从静态 Mock 重写为实时 API 交互：增删改查 + CSV 导出 + 编辑内联表单
- 前端 `api.ts` 新增 Database CRUD 接口封装（`fetchDbTables`/`queryDbTable`/`insertDbRow`/`updateDbRow`/`deleteDbRow`）
- chat 和 DB 端点增加结构化 Loguru 日志

### Fixed

- `init_db()` Alembic 成功后直接 return 导致新增 ORM 表（Experiment/Sample/Device）未创建、种子数据未填充
- 前端数据管理面板「新增/编辑/删除」均为 alert("接口预留")，现已接入后端 API

### Changed

- 版本号全量统一为 0.15.0（8 处）
- README.md 功能状态表诚实标注（✅可用 / 🔧已实现 / ⚠️Mock / 🔌预留）
- PROJECT_STATUS.md 全面重写，新增 v0.15.0 变更记录

## [0.14.1] - 2026-08-08

### Added

- 一键启动器：`start.py`（跨平台）、`start.bat`、`stop.bat`
- 自动检测 Python 3.12+ / Node.js 22+ 环境
- 自动创建虚拟环境、安装依赖、生成 `.env` 配置
- 端口占用检测，服务就绪后自动打开浏览器

## [0.14.0] - 2026-08-08

### Added

- 网页填表模块：`web_tools.py`（浏览/填表/文本提取）
- 网页操作 REST API：`/api/v1/web/browse`、`fill-form`、`extract-text`
- 前端「网页填表」Tab + `WebFormPanel.tsx`
- 会话标题自动生成（首条消息前 20 字）
- UUID 简化显示（截取后 8 位）

### Fixed

- 会话列表不刷新、LLM 不知道图表已生成、新建会话异常、会话 ID 显示乱码、文件预览路径错误

## [0.13.0] - 2026-08-08

### Added

- 数据管理模块：`db.py`（业务数据 CRUD API）
- 前端「数据管理」Tab + `DatabasePanel.tsx`
- 预置实验数据演示（柴油加氢脱硫、催化裂化催化剂筛选等）

## [0.12.0] - 2026-08-08

### Added

- 硬件设备模块：`hardware_tools.py`（查询状态/下发指令）
- 硬件 REST API：`/api/v1/hardware/devices`（列表/详情/指令）
- 前端「硬件设备」Tab + `HardwarePanel.tsx`
- 5 种预置设备 + 实时指标随机漂移模拟

## [0.11.0] - 2026-08-08

### Added

- Office 文档处理：`office_tools.py`（Excel/Word/PPT 读写）
- 图表生成：`chart_tools.py`（折线/柱状/散点/饼图/面积图）
- 文件预览 API：`/api/v1/files/preview`
- 前端「文件管理」Tab + `FileBrowser.tsx`（Excel/Word/PPT 预览组件）
- 依赖新增：openpyxl、python-docx、python-pptx、matplotlib

## [0.10.0] - 2026-08-08

### Added

- 前端聊天 UI：`ChatWindow.tsx`（SSE 流式 + 打字机效果）
- 消息组件：`Message.tsx`、`MessageList.tsx`、`MessageInput.tsx`
- 会话管理：`Sidebar.tsx`（列表/切换/删除）
- API 服务层：`services/api.ts`（对话/会话/LLM/文件接口）
- TypeScript 类型定义：`types/index.ts`

## [0.9.0] - 2026-08-08

### Added

- Alembic 数据库迁移框架（配置 + 环境 + 迁移脚本模板）
- 初始迁移脚本 `001_initial_tables.py`（users/sessions/messages/tool_audits/knowledge 五表）
- 迁移管理脚本 `scripts/migrate.py`（upgrade/downgrade/current/history/create/drop）

## [0.8.0] - 2026-08-08

### Added

- Agent 内核：`manager.py`、`executor.py`、`planner/planner.py`、`memory/memory.py`
- LLM 系统提示词：`prompts/prompts.py`（默认 + 石油化工领域专用）
- 对话 API：`/api/v1/chat`（同步 + SSE 流式 + 会话管理）
- ORM 模型：`tables.py`（User/Session/Message/ToolAudit/Knowledge）
- 安全护栏：`input_guard.py`、`output_guard.py`、`permission.py`
- MCP 客户端框架：`mcp/client.py`

## [0.3.0] - 2026-08-08

### Added

- 工具注册表：`registry.py`（@register_tool 装饰器）
- 工具基类：`base.py`、工具管理器：`manager.py`
- 文件系统工具：`file_tools.py`（读/写/追加/列表/删除 + 路径安全）
- 文件监听服务：`file_watcher.py`（watchdog + 防抖 + 发布订阅）
- 文件管理 API：`/api/v1/files`（REST + WebSocket 实时推送）

## [0.2.0] - 2026-08-08

### Added

- LLM 客户端：`llm/client.py`（重试 + 指数退避）
- LLM 提供商抽象：`llm/provider.py`（OpenAI / Ollama）
- LLM 数据模型：`llm/schemas.py`
- LLM 管理端点：`/api/v1/llm/test`、`/api/v1/llm/info`
- 全局配置扩展：LLM + 文件系统配置项

## [0.1.0] - 2026-08-08

### Added

- 项目初始化：FastAPI 后端 + React/Vite 前端
- 后端骨架：核心模块占位（agent/llm/tools/database/guardrails/mcp）
- 前端骨架：基础布局 + 样式
- Docker 部署配置：backend / frontend / nginx
- 基础设施：健康检查、根路由、CORS、日志系统
