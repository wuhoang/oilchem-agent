# OilChem Agent

> 石油化工智能实验室 Agent 平台 —— 连接「人 · 硬件 · 软件 · 网页」的中间层。

![version](https://img.shields.io/badge/version-1.0.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![python](https://img.shields.io/badge/Python-3.12-blue)
![react](https://img.shields.io/badge/React-18-blue)
![status](https://img.shields.io/badge/status-prototype-orange)

OilChem Agent 是一个面向石油化工/化学实验室的 AI 助手：通过自然语言对话，完成实验数据查询与可视化、Office 文档处理、硬件设备状态监控、网页自动化填表等工作。

> **当前状态：** 原型阶段。Agent 管线 / LLM 对话 / 文件与 Office 工具 / 数据管理已可用；硬件设备当前使用模拟数据，真实硬件通信（RS232/USB/GPIB）为后续预留。
> **更新日志：** 详见 [CHANGELOG.md](CHANGELOG.md)

---

## 它能帮你做什么

| 场景 | 示例 |
|------|------|
| 📊 **实验数据可视化** | 「把这份实验数据画成趋势图」→ 自动读取数据文件 → 解析曲线 → 生成图表 |
| 🔬 **实验记录管理** | 实验记录、样品、设备的增删改查，SQLite 持久化，支持 CSV 导出 |
| 📁 **Office 文档处理** | 读取/生成 Excel、Word、PPT，如「把这份实验数据整理成 Excel 表格」 |
| 🏭 **设备状态监控** | 实时查看 5 台模拟设备的温度/压力/液位等指标，查询历史趋势并画图 |
| 🌐 **网页自动化** | 浏览网页、智能填写表单（登录、录入数据），基于 Playwright |
| 🛡️ **安全护栏** | Prompt 注入检测、敏感信息脱敏、有害内容过滤 |

---

## 架构一图流

```
┌──────────────────┐   HTTP/SSE   ┌───────────────────┐
│  React SPA       │ ───────────▶ │  FastAPI backend  │
│  (frontend/)     │ ◀─────────── │  (backend/app/)   │
└──────────────────┘   JSON       └─────────┬─────────┘
                                            │
         ┌──────────────────────────────────┤
         ▼                                  ▼
  ┌─────────────┐                   ┌───────────────┐
  │  LLM Client │                   │  AgentManager │
  │ (DeepSeek / │                   │  ┌─────────┐  │
  │  OpenAI兼容)│                   │  │ Planner │  │
  └─────────────┘                   │  │Executor │  │
                                    │  │ Memory  │  │
  ┌─────────────┐                   │  └─────────┘  │
  │ 19 个工具    │ ◀──── 调用 ───────┤               │
  │ (文件/Office │                   │  ToolManager  │
  │  图表/网页/  │                   └───────────────┘
  │  硬件)      │
  └─────────────┘
```

---

## 功能特性

| 模块 | 说明 | 状态 |
|------|------|------|
| 💬 智能对话 | SSE 流式对话、多会话管理、Agent 规划-执行-记忆管线 | ✅ 可用 |
| 🛡️ 安全护栏 | Prompt 注入检测、敏感信息脱敏、输出过滤 | ✅ 已接入 |
| 📁 文件管理 | 文本读写、目录浏览、Office 预览、文件监听 | ✅ 可用 |
| 📊 图表生成 | matplotlib 可视化，base64 在前端自动渲染 | ✅ 可用 |
| 🌐 网页填表 | Playwright 浏览器自动化：浏览、智能填表、内容提取 | ✅ 可用 |
| 💾 数据管理 | 实验记录/样品/设备 CRUD，SQLAlchemy ORM 持久化 | ✅ 可用 |
| 🔌 硬件设备 | 设备列表、实时指标采集、历史趋势查询 | ⚠️ Mock 数据 |
| 🔐 用户认证 | JWT 配置就绪 | 🔌 预留 |

---

## 快速开始

### 🚀 一键启动（推荐）

**方式一：双击启动（Windows）**

直接双击 `start.bat`，首次运行会自动：
1. 检查 Python 3.12+ 和 Node.js 22+ 是否已安装
2. 创建后端虚拟环境 `backend/.venv`
3. 安装所有 Python 依赖和 npm 依赖
4. 生成 `backend/.env` 配置文件
5. 启动后端（端口 8000）和前端（端口 5173）
6. 自动打开浏览器访问 `http://localhost:5173`

**方式二：命令行启动**

```bash
# Windows
python start.py

# Linux / macOS
python3 start.py
```

**停止服务：** 双击 `stop.bat` 一键停止所有服务。

### 手动启动

**后端：**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置 LLM 提供商、模型名称、文件路径等
python -m app.main
# → http://localhost:8000
# Swagger 文档：http://localhost:8000/docs
```

**前端：**

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## API 路由一览

### 系统

| Method | Path | 说明 |
|--------|------|------|
| GET | `/` | 应用信息（版本、状态） |
| GET | `/health` | 健康检查 |
| GET | `/docs` | Swagger UI |

### LLM 管理

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/llm/test` | LLM 连通性测试 |
| GET | `/api/v1/llm/info` | LLM 配置信息 |

### 智能对话

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/chat` | 同步对话（Agent 全流程） |
| POST | `/api/v1/chat/stream` | SSE 流式对话 |
| GET | `/api/v1/chat/sessions` | 获取会话列表 |
| GET | `/api/v1/chat/sessions/{id}` | 获取单个会话详情 |
| DELETE | `/api/v1/chat/sessions/{id}` | 删除会话 |

### 文件管理

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/files/read` | 读取文件（支持行范围） |
| POST | `/api/v1/files/write` | 写入文件（覆盖） |
| POST | `/api/v1/files/append` | 追加文件内容 |
| POST | `/api/v1/files/list` | 列出目录内容（支持递归/glob） |
| POST | `/api/v1/files/delete` | 删除文件 |
| POST | `/api/v1/files/preview` | 预览文件（支持 Excel/Word/PPT） |
| GET | `/api/v1/files/tools` | 列出可用工具 |
| POST | `/api/v1/files/watch/start` | 启动文件监听 |
| POST | `/api/v1/files/watch/stop` | 停止文件监听 |
| WS | `/ws/files/events` | 文件变化事件推送 |

### 网页操作

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/web/browse` | 浏览网页，返回内容 + 表单 + 截图 |
| POST | `/api/v1/web/fill-form` | 自动登录 + 填写表单 + 提交 |
| POST | `/api/v1/web/extract-text` | 提取网页文本内容 |

### 硬件设备

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/hardware/devices` | 列出所有设备（含实时指标） |
| GET | `/api/v1/hardware/devices/{id}` | 获取单个设备详情 |
| POST | `/api/v1/hardware/devices/{id}/command` | 下发设备指令 |

### 数据管理

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/db/tables` | 列出业务表 |
| POST | `/api/v1/db/{table}/query` | 查询表数据（支持关键字搜索） |
| POST | `/api/v1/db/{table}/insert` | 插入一行数据 |
| POST | `/api/v1/db/{table}/update` | 更新一行数据 |
| DELETE | `/api/v1/db/{table}/delete` | 删除一行数据 |

---

## 配置说明

### LLM 配置

在 `backend/.env` 中配置 LLM 提供商。**当前默认使用 DeepSeek API**（通过 OpenAI 兼容接口）：

```env
# 方式 A：DeepSeek API（当前默认）
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-你的-deepseek-key
MODEL_NAME=deepseek-chat
LLM_TIMEOUT=30.0
LLM_MAX_RETRIES=2
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# 方式 B：本地 Ollama（无需 API Key，备用方案）
# LLM_PROVIDER=ollama
# OPENAI_BASE_URL=http://localhost:11434
# OPENAI_API_KEY=
# MODEL_NAME=qwen2.5
```

验证连通性：`GET /api/v1/llm/test`

如需切换本地 Ollama 模型：
1. 安装 [Ollama](https://ollama.com)
2. 拉取模型：`ollama pull qwen2.5`
3. 启动 Ollama：`ollama serve`
4. 修改 `.env` 使用方式 B，重启后端

### 文件系统配置

```env
# 允许操作的路径白名单（逗号分隔，留空则允许所有路径）
FILE_ALLOWED_PATHS=C:\data,C:\reports

# 自动监听的路径（逗号分隔）
FILE_WATCH_PATHS=C:\data

# 防抖时间（毫秒）
FILE_DEBOUNCE_MS=2000
```

### 数据库配置

```env
DATABASE_URL=sqlite+aiosqlite:///./oilchem_agent.db
DB_ECHO=false
```

启动时自动执行 Alembic 迁移并填充种子数据。手动操作：

```bash
cd backend
python -m scripts.migrate upgrade       # 升级到最新
python -m scripts.migrate downgrade     # 回滚一个版本
python -m scripts.migrate current       # 查看当前版本
python -m scripts.migrate history       # 迁移历史
python -m scripts.migrate create "描述" # 创建新迁移
python -m scripts.migrate drop          # 回退到初始
```

### 认证配置

```env
AUTH_ENABLED=false
JWT_SECRET_KEY=change-me-in-production
JWT_EXPIRE_MINUTES=60
```

### 硬件采集配置

```env
HARDWARE_COLLECT_INTERVAL=10          # 遥测采集间隔（秒）
HARDWARE_HISTORY_RETENTION_MINUTES=1440  # 历史数据保留窗口（分钟）
```

### Office 依赖安装

```bash
pip install openpyxl python-docx python-pptx
```

这些库已在 `requirements.txt` 中声明。

### 网页填表依赖安装

```bash
pip install playwright
playwright install chromium
```

---

## 前端功能

| Tab | 功能 |
|-----|------|
| **智能对话** | 💬 与 Agent 实时对话（SSE 流式），多会话管理，工具自动调用 |
| **文件管理** | 📁 浏览目录、读写文本文件、预览 Excel/Word/PPT |
| **硬件设备** | 🔌 查看模拟设备列表与实时指标（当前为 Mock 数据，未接真实硬件） |
| **数据管理** | 💾 实验记录/样品/设备的 CRUD，SQLAlchemy + SQLite 持久化 |
| **网页填表** | 🌐 Playwright 浏览器自动化：网页浏览、智能填表、内容提取 |

### 会话管理

- **标题自动生成**：基于首条消息前 20 字自动生成会话标题
- **UUID 简化显示**：会话列表中截取 UUID 后 8 位作为标识
- **消息数实时更新**：对话结束后自动刷新侧边栏
- **排序**：按 `updated_at` 倒序排列

---

## Agent 工具系统（19 个）

Agent 内置以下工具，可在对话中自动调用：

### 文件操作

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容（支持行范围、二进制检测） |
| `write_file` | 写入文件（覆盖） |
| `append_file` | 追加内容到文件 |
| `list_files` | 列出目录内容（支持递归和 glob） |
| `delete_file` | 删除文件（安全限制，不删目录） |

### Office 文档

| 工具 | 说明 |
|------|------|
| `read_excel` | 读取 Excel 表格数据 |
| `write_excel` | 写入 Excel 表格数据 |
| `read_word` | 提取 Word 文档段落和表格 |
| `write_word` | 写入 Word 文档 |
| `read_ppt` | 解析 PPT 幻灯片文本 |
| `write_ppt` | 写入 PPT 演示文稿 |

### 硬件设备

| 工具 | 说明 |
|------|------|
| `read_hardware` | 读取设备实时指标快照 |
| `query_hardware_history` | 查询设备历史趋势数据（支持降采样） |
| `send_hardware_command` | 向硬件设备下发指令 |

### 图表与网页

| 工具 | 说明 |
|------|------|
| `plot_chart` | 生成 matplotlib 图表（折线图/柱状图/散点图等） |
| `browse_webpage` | 浏览网页并提取内容、表单、截图 |
| `smart_fill_form` | 智能识别并填写网页表单 |
| `fill_webform` | 自动登录并填写网页表单 |
| `extract_webpage_text` | 提取网页文本内容 |

---

## 文件监听

1. 在 `.env` 中配置 `FILE_WATCH_PATHS`
2. 启动后端后自动启动监听
3. 连接 WebSocket `ws://localhost:8000/ws/files/events` 接收事件

事件格式：
```json
{
  "type": "file_change_batch",
  "total_events": 3,
  "aggregated": {
    "created": ["/path/new_file.txt"],
    "modified": ["/path/changed.csv"],
    "deleted": [],
    "moved": []
  },
  "timestamp": 1712500000.0
}
```

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端框架** | FastAPI + Uvicorn | Python 3.12 |
| **数据校验** | Pydantic v2 + Pydantic Settings | 2.9.2 |
| **LLM 交互** | HTTPX（支持 Ollama/OpenAI 兼容接口） | 0.27.2 |
| **数据库** | SQLAlchemy + aiosqlite + Alembic | 2.0.36 |
| **Office 处理** | openpyxl / python-docx / python-pptx | — |
| **图表生成** | matplotlib（后端绑定） | — |
| **浏览器自动化** | Playwright（后端绑定） | — |
| **文件监听** | Watchdog | 3.0.0 |
| **日志** | Loguru | 0.7.2 |
| **前端框架** | React + Vite + TypeScript | Node.js 22 |
| **样式** | TailwindCSS | — |
| **包管理** | pip / npm | — |

---

## 仓库结构

```
oilchem-agent/
├── backend/                          # 后端 — FastAPI + Python 3.12
│   ├── app/
│   │   ├── agent/                    #   Agent 内核
│   │   │   ├── manager.py            #     Agent 管理器（协调 LLM + 工具 + 记忆）
│   │   │   ├── memory/memory.py      #     会话记忆管理
│   │   │   ├── planner/planner.py    #     任务规划器
│   │   │   ├── executor.py           #     计划执行器
│   │   │   └── prompts/prompts.py    #     系统提示词
│   │   ├── api/v1/endpoints/         #   REST + SSE 端点
│   │   │   ├── chat.py               #     对话 API（同步/流式/会话管理）
│   │   │   ├── files.py              #     文件管理 API + WebSocket 监听
│   │   │   ├── web.py                #     网页操作 API（浏览/填表/提取）
│   │   │   ├── hardware.py           #     硬件设备 API
│   │   │   ├── db.py                 #     业务数据 CRUD API
│   │   │   ├── llm.py                #     LLM 连通性测试
│   │   │   ├── system.py             #     系统信息
│   │   │   └── health.py             #     健康检查
│   │   ├── core/                     #   配置、日志、安全
│   │   ├── llm/                      #   LLM 客户端 + 提供商抽象
│   │   ├── tools/builtin/            #   19 个内置工具（注册表 + 管理器）
│   │   ├── services/                 #   后台服务（文件监听 / 硬件遥测采集）
│   │   ├── database/                 #   SQLAlchemy 会话管理 + 种子数据
│   │   ├── guardrails/               #   输入/输出护栏 + RBAC
│   │   ├── mcp/                      #   MCP 集成框架（预留）
│   │   └── schemas/                  #   共享 Pydantic 模型
│   ├── alembic/                      #   数据库迁移
│   ├── scripts/migrate.py            #   迁移管理脚本
│   ├── requirements.txt              #   Python 依赖
│   ├── .env.example                  #   环境变量模板
│   └── alembic.ini
├── frontend/                         # 前端 — React + Vite + TypeScript
│   └── src/
│       ├── types/index.ts            #   TypeScript 类型定义
│       ├── services/api.ts           #   API 服务层
│       ├── components/               #   对话/文件/硬件/数据/网页填表面板
│       └── App.tsx                   #   根组件 + Tab 导航
├── docs/                             # 架构 / 路线图 / API 文档
├── hardware_info/                    # 硬件演示数据（模拟指标样例）
├── CHANGELOG.md                      # 更新日志
├── DEVELOPMENT_LOG.md                # 开发日志
└── LICENSE
```

---

## Git 工作流

- `main` — 稳定版，生产环境
- `develop` — 集成分支
- `feature/*` — 短期功能分支

---

## 相关文档

- [架构设计](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [API 文档](docs/api.md)
- [项目状态](docs/PROJECT_STATUS.md)
- [更新日志](CHANGELOG.md)
- [开发日志](DEVELOPMENT_LOG.md)

## License

[MIT](LICENSE)
