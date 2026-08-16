# CLAUDE.md

## 全局通用行为准则（减少常见 LLM 编码错误）

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 目录注意事项

以下目录不在版本控制中，体量巨大（合计 >6GB），**日常搜索/Grep/Glob 默认排除**，误扫会瞬间烧掉数万 token：

- `backend/.venv/` — 3.9GB，Python 依赖
- `frontend/node_modules/` — 2.5GB，Node 依赖
- `backend/.playwright-browsers/` — Chromium/Firefox 浏览器二进制
- `.git/` — Git 仓库数据

**平时搜索限定在源码目录**：`./backend/app/`、`./backend/tests/`、`./frontend/src/`、`./docs/`、`./backend/alembic/`、`./backend/scripts/`。

如果排查依赖冲突、包版本问题、构建错误时需要查看上述目录中的具体文件，可以看——但必须有明确目标文件路径，**严禁**在 `.venv/` 或 `node_modules/` 中做模糊搜索（如 `grep "some_pattern" .venv/`）。

## 项目

**OilChem Agent** — 石油化工/化学实验室 AI 助手，定位为「人-硬件-软件-网页」的中间层。

- 当前版本：1.2.0，在 `develop` 分支开发
- 技术栈：Python 3.12 + FastAPI + SQLAlchemy (aiosqlite) | React 18 + TypeScript + Vite + TailwindCSS
- **实际使用的 LLM**：DeepSeek API（`deepseek-chat`，通过 OpenAI 兼容接口）。配置在 `backend/.env`，**不在代码里**
- 代码层同时预留了本地 Ollama Provider（可用 `qwen2.5` 等），但**当前默认和实际运行都是 DeepSeek**，不要假设系统用本地小模型
- 用户背景：油化领域出身，软件不太熟但对硬件接口更了解

## 架构速览

```
frontend/ (React SPA, :5173)  ──HTTP/SSE──▶ backend/ (FastAPI, :8000)
                                                │
   ★ Agent 管线 ★                                   │
   AgentManager ─ function calling ─▶ 25个工具        │
               ─▶ Memory(纯内存会话)                  │
   （旧 Planner→Executor 链路保留，未挂主链路）        │
                                                │
   /api/v1/chat  +  /api/v1/chat/stream        │
   /api/v1/db/*  +  /api/v1/llm/*              │
   /api/v1/web/*  +  /api/v1/files/*           │
   /api/v1/hardware/*  +  /api/v1/experiments/*│
```

## 常用命令

```bash
# 后端
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend && npm run dev

# 一键启动
python start.py

# 测试
cd backend && .venv/Scripts/python.exe -m pytest tests/test_bootstrap.py -v

# 数据库（SQLite 文件在 backend/oilchem_agent.db）
删除 .db 文件后重启后端会自动重建 + 填充种子数据
```

## 当前真实状态

| 状态 | 模块 |
|------|------|
| ✅ 可用 | FastAPI 骨架、LLM 客户端 (OpenAI 兼容/DeepSeek + Ollama 预留)、Playwright 网页工具 (browse/smart_fill)、对话端点 (含 SSE)、Guardrails 已接入 chat 端点、DB 端点已接入 ORM (SQLite)、**实验域 M1-M7 端到端闭环** (编排器 orchestrator / 报告生成 / SSE 事件 / 追溯审计) |
| 🔧 已实现未验证 | 25个工具中除已验证之外的其余工具、文件监听 (watchdog) |
| 🔧 备用链路 | 旧 Planner→Executor（手写 JSON 计划），代码保留但主链路已改用 function calling，不再使用 |
| ⚠️ Mock | 硬件设备 (油化仿真设备源统一到 DriverRegistry，驱动仍是 MockDriver 模拟器，指令为模拟下发)、DB users 表在 ORM 但未接认证 |
| 🔌 预留 | 用户认证 (AUTH_ENABLED=false)、MCP 客户端 (写了没接)、真实硬件通信 (RS232/USB/GPIB) |

## 重要文件

| 模块 | 路径 |
|------|------|
| 编排引擎（实验状态机） | `backend/app/services/orchestrator.py` |
| 设备驱动层 | `backend/app/hardware/drivers/{base,mock,registry}.py`（抽象接口 / 剧本引擎 / 单一设备源） |
| 报告生成 | `backend/app/services/report_generator.py`（Word + Excel，存 `storage/reports/{id}/`） |
| 实验域工具 | `backend/app/tools/builtin/experiment_tools.py`（6 个工具） |
| 实验域 API | `backend/app/api/v1/endpoints/experiments.py`（REST + SSE） |
| Agent 主循环 | `backend/app/agent/manager.py`（function calling，`max_iterations=8`） |
| 前端实验中心 | `frontend/src/components/ExperimentCenter.tsx`（三视图 + EventSource SSE） |
| 设备仿真数据 | `backend/app/hardware/hardware_simulation_data.json`（6 台油化仿真设备剧本曲线） |

## 架构决策

- **工具决策用非流式** `chat()`，最终文本回复才用流式 `stream_chat()`——规避流式 `tool_calls` 增量累积的复杂度
- **tool 往返不写 Memory**：工具结果只在当次循环内回传，不持久化，避免污染后续多轮对话
- **图片 base64 不进 LLM 上下文**：工具返回图片时经 `_sanitize_tool_output` 转文字描述，图片本身只走 SSE `chart` 事件给前端
- **`init_db()` 三阶段**：Alembic → create_all(幂等补建) → seed(幂等填充)，不得回退到早 return
- **Playwright 走后台线程** `_SyncBrowserManager`，勿改用 async API（Windows greenlet 跨线程错误）

## 项目规则

### 版本号
改代码涉及版本变化时，统一更新这 9 处（注：`backend/.env` 被 gitignore，仅本地生效，改它是为了让本地运行时版本显示一致）：
- `backend/pyproject.toml`、`backend/.env` (APP_VERSION)
- `backend/app/core/config.py`、`backend/app/core/constants.py`
- `frontend/package.json`、`frontend/package-lock.json`
- `frontend/src/App.tsx`、`frontend/src/components/Sidebar.tsx`
- `docs/api.md`

### 文档更新
每次改动后同步更新：
- `CHANGELOG.md` — 按 Added/Fixed/Changed 格式追加
- `DEVELOPMENT_LOG.md` — 详细版变更日志
- `docs/PROJECT_STATUS.md` — 逐模块状态表
- `README.md` — 如有功能状态变化

### 代码风格
- Python: `from __future__ import annotations`，Pydantic v2 模型，Loguru 日志（`logger.bind(component="xxx")` 结构化）
- 前端: React 函数组件 + hooks，TypeScript，API 调用封装在 `services/api.ts`
- 日志: 所有新增端点/工具调用加 Loguru 日志，级别按 info/warning/error
- 注释: 不要无意义注释。公共 API 用 docstring，内部逻辑只在反直觉时加注

### 测试
- 目前仅 2 个 smoke test (`backend/tests/test_bootstrap.py`)
- 改完代码至少跑一遍确认不过不了
- 如果改了 DB/chat 端点，用 TestClient 实际测一下 API 调用

### 关键已知问题
- **主链路已改用原生 function calling**：模型直接输出 `tool_calls`，不依赖 LLM 产出 JSON 计划。旧的 Planner→Executor 链路（依赖 `_extract_json_object()` 三层容错解析 JSON 计划）代码仍保留，但已不在主链路；只有切回旧链路时才需要考虑 JSON 容错问题
- **MemoryManager 纯内存**，进程重启全部丢失，不是 Bug 是设计如此（还没做持久化）
- **`send_hardware_command` 仍无真实硬件通信**：工具 → DriverRegistry 取 MockDriver → `driver.send_command()` 返回 `{"status":"queued","message":"...（模拟）"}`。走的是模拟器，未接真实 RS232/USB/GPIB
- **`init_db()` 三阶段执行**：Alembic → create_all(幂等补建) → seed(幂等填充)。不要回退到早 return 模式，否则新增 ORM 表不会创建
- **Playwright 在后台线程 + 任务队列模式运行**（`_SyncBrowserManager`），不要试图改用 async API，会触发 Windows greenlet 跨线程错误

### 用户偏好
- 用户对软件工程不太熟，解释技术概念时用白话、用类比
- 用户更信任看得见的东西（前端界面 > 测试结果 > 日志 > 代码逻辑）
- 每次改动后主动问要不要跑起来看看
- 评估项目状态时实事求是，不美化不贬低
- 不要擅自创建文档文件（.md）除非明确要求

### 每次改动后必做检查清单
代码改完之后，主动检查以下内容，有遗漏就补上，不需要等用户提醒：
1. **版本号**：涉及功能变化时，检查 9 处版本号是否都已更新（见上方"版本号"章节）
2. **CHANGELOG.md**：按 Added/Fixed/Changed 格式追加本次变更
3. **DEVELOPMENT_LOG.md**：补充详细变更记录
4. **docs/PROJECT_STATUS.md**：逐模块状态表如有变化要同步更新
5. **README.md**：如有功能状态变化要更新状态表
6. **docs/api.md**：如有 API 变更要同步更新
7. **docs/architecture.md**：如有架构变化要同步更新

纯 bug 修复、小调整、代码重构等不影响功能/接口的改动，至少检查第 1、2 项。
