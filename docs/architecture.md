# OilChem Agent — Architecture

## High-level

```
┌────────────────────┐    HTTP/SSE  ┌────────────────────┐
│  React + Vite SPA  │ ───────────▶ │  FastAPI backend   │
│  (frontend/)       │ ◀─────────── │  (backend/app/)    │
└────────────────────┘   JSON/SSE   └────────┬───────────┘
                                              │
          ┌───────────────────────────────────┼───────────────────────────┐
          ▼                                   ▼                           ▼
 ┌──────────────────┐              ┌──────────────────────┐    ┌──────────────────┐
 │  LLM Client      │              │  AgentManager         │    │  Hardware Collector│
 │  (app/llm/)      │              │  (function calling)   │    │  (后台遥测采集)    │
 └──────────────────┘              └──────────┬───────────┘    └────────┬─────────┘
                                               │                          │
                    ┌──────────────────────────┼──────────────┐           │
                    ▼                          ▼              ▼           ▼
           ┌──────────────┐          ┌──────────────────┐  ┌──────────────┐
           │ ToolManager  │          │  Orchestrator    │  │ DriverRegistry│
           │ (25 tools)   │          │  编排引擎(M2)    │  │ (6台油化仿真  │
           └──────┬───────┘          │  状态机+主循环   │  │  设备统一源)  │
                  │                  └────────┬─────────┘  └──────┬───────┘
                  │                           │ 执行步骤          │ 遥测
                  ▼                           ▼                   ▼
           ┌──────────────────────────────────────────────────────────┐
           │  Database (SQLAlchemy + aiosqlite, 16 张表)                │
           │  User/Session/Message/ToolAudit/Knowledge                │
           │  + Experiment/Sample/Device/DeviceTelemetryHistory       │
           │  + ExperimentAudit/Experimenter/Protocol/ProtocolStep    │
           │  + Material/ExperimentStep/Measurement                   │
           └──────────────────────────────────────────────────────────┘
```

## Backend layout

| Layer          | Path                          | Step 8 state           |
|----------------|-------------------------------|------------------------|
| Entry point    | `app/main.py`                 | Implemented            |
| Config         | `app/core/config.py`          | Implemented            |
| Logging        | `app/core/logger.py`          | Implemented            |
| API root       | `app/api/v1/router.py`        | Implemented            |
| **LLM**        | `app/llm/`                    | **Implemented** ✅      |
| **Agent**      | `app/agent/`                  | **Implemented** ✅      |
| **Tools**      | `app/tools/`                  | **Implemented** ✅      |
| **Services**   | `app/services/`               | **Implemented** ✅      |
| **Database**   | `app/database/`               | **Implemented** ✅      |
| **Models**     | `app/models/`                 | **Implemented** ✅      |
| **Guardrails** | `app/guardrails/`             | **Implemented** ✅      |
| **MCP**        | `app/mcp/`                    | **Implemented** ✅      |
| **Alembic**    | `alembic/`                    | **Implemented** ✅ Step 8 |
| **Scripts**    | `scripts/migrate.py`          | **Implemented** ✅ Step 8 |

## Tools 模块架构

```
┌─────────────────────────────────────────────┐
│            app/tools/manager.py             │
│            ToolManager (入口)               │
│  - execute() / list_available_tools()      │
└──────────────────┬──────────────────────────┘
                   │ 查找
                   ▼
┌─────────────────────────────────────────────┐
│          app/tools/registry.py              │
│          工具注册表                          │
│  - @register_tool 装饰器                    │
│  - get_tool_class() / list_tools()          │
└──────────────────┬──────────────────────────┘
                   │ 创建
                   ▼
┌─────────────────────────────────────────────┐
│          app/tools/base.py                  │
│          BaseTool (抽象基类)                │
│  - ToolMetadata / ToolResult                │
│  - async execute(**kwargs)                  │
└──────────────────┬──────────────────────────┘
                   │ 继承
                   ▼
┌─────────────────────────────────────────────┐
│      app/tools/builtin/file_tools.py        │
│      内置文件工具                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │read_file │  │write_file│  │append_file│  │
│  └──────────┘  └──────────┘  └──────────┘  │
│  ┌──────────┐  ┌──────────┐                │
│  │list_files│  │delete_file│                │
│  └──────────┘  └──────────┘                │
└─────────────────────────────────────────────┘
```

## 实验域架构（M1-M7）

```
┌─────────────────────────────────────────────────────────────┐
│          app/services/orchestrator.py (M2 编排引擎)          │
│  - 实验状态机: 草稿→待执行→执行中→完成/异常/中止            │
│  - 步骤展开(protocol_steps → experiment_steps)              │
│  - 主循环执行 + 异常冻结/重试/跳步/中止                      │
│  - SSE 事件广播(experiment_status/step_status/measurement)  │
└──────┬──────────────────────────────┬───────────────────────┘
       │ acquire/release              │ 完成时
       ▼                              ▼
┌─────────────────────┐   ┌─────────────────────────────┐
│ DriverRegistry (M3) │   │ report_generator.py (M7)    │
│  6台油化仿真设备     │   │  Word 报告 + Excel 数据表    │
│  ┌───────────────┐ │   │  存 storage/reports/{id}/     │
│  │ MockDriver    │ │   └─────────────────────────────┘
│  │ (剧本引擎)    │ │
│  │ - 升温/恒温   │ │
│  │ - 漏失量曲线  │ │
│  │ - reset()     │ │
│  └───────────────┘ │
└─────────────────────┘

数据模型(M1): 16 张表
  实验员 Experimenter → 方案 Protocol → 方案步骤 ProtocolStep
  实验 Experiment(含 result/report_path) → 步骤实例 ExperimentStep
  物料 Material ← 样品 Sample；测量 Measurement；审计 ExperimentAudit
```

## File Watcher 架构

```
┌─────────────────────────────────────────────┐
│        app/services/file_watcher.py         │
│        FileWatcherService (单例)            │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  PollingObserver (watchdog)         │    │
│  │  ├── Folder A → FileChangeHandler  │    │
│  │  └── Folder B → FileChangeHandler  │    │
│  └──────────────┬──────────────────────┘    │
│                 │ 事件入队                   │
│                 ▼                            │
│  ┌─────────────────────────────────────┐    │
│  │  DebouncedEventProcessor            │    │
│  │  └─ 防抖合并 → 批量事件             │    │
│  └──────────────┬──────────────────────┘    │
│                 │ 分发                       │
│                 ▼                            │
│  ┌─────────────────────────────────────┐    │
│  │  订阅者队列 (WebSocket 连接)        │    │
│  │  ├── WS Client 1 → 推送事件        │    │
│  │  └── WS Client 2 → 推送事件        │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

## LLM 模块架构

```
┌─────────────────────────────────────────────┐
│              app/llm/client.py               │
│              LLMClient (入口)                │
│  - 重试 + 指数退避                           │
│  - 日志 + 错误处理                           │
│  - chat() / stream_chat() / test_connection() │
└──────────────────┬──────────────────────────┘
                   │ 委托
                   ▼
┌─────────────────────────────────────────────┐
│            app/llm/provider.py               │
│          BaseProvider (抽象基类)             │
│  ┌──────────────┐  ┌──────────────┐         │
│  │OpenAIProvider│  │OllamaProvider│         │
│  └──────────────┘  └──────────────┘         │
│  - 提供商注册表 + 装饰器注册                  │
│  - 请求构造 / 响应解析 / SSE / NDJSON        │
└──────────────────┬──────────────────────────┘
                   │ 使用
                   ▼
┌─────────────────────────────────────────────┐
│            app/llm/schemas.py               │
│            Pydantic 数据模型                 │
│  - ChatMessage / ChatCompletionRequest       │
│  - ChatCompletionResponse / Usage            │
│  - StreamChunk / StreamDelta                 │
│  - ProviderConfig                            │
└─────────────────────────────────────────────┘
```

## Alembic 迁移架构

```
┌─────────────────────────────────────────────┐
│           alembic.ini (根目录)               │
│           主配置文件（script_location 等）    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│        alembic/env.py (环境配置)             │
│  - 自动加载 models → Base.metadata          │
│  - 从 settings 解析 database_url             │
│  - aiosqlite → sqlite 同步 URL 转换          │
│  - SQLite batch 模式                         │
│  - offline / online 双模式                   │
└──────────────────┬──────────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│ versions/001..004│  │  scripts/        │
│ 4 个迁移脚本      │  │  migrate.py     │
│ (upgrade/downgrade)│ │ 便捷管理命令     │
└──────────────────┘  └──────────────────┘
```

迁移流程：
1. 启动时 `init_db()` → 优先 Alembic upgrade（后台线程）
2. Alembic 失败 → 回退到 `Base.metadata.create_all`
3. 开发时通过 `python -m scripts.migrate` 手动管理

## Branching

- `main`    — stable, releasable
- `develop` — integration branch
- feature/* — short-lived topic branches off `develop`