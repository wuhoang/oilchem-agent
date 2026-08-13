# OilChem Agent

石油化工领域的企业级 Agent 平台。集成 LLM 对话、Office 文档处理、硬件设备管理、数据管理、网页填表等能力，为人-机-物协同提供中间层解决方案。

> **当前版本：** v0.16.2
> **状态：** 原型阶段 — Agent 骨架/LLM/Playwright 网页工具可用，硬件与部分 DB 端点仍为 Mock 数据
> **更新日志：** 详见 [CHANGELOG.md](CHANGELOG.md)

---

## 功能特性

| 模块 | 说明 | 状态 |
|------|------|------|
| 💬 智能对话 | SSE 流式对话、多会话管理、工具调用、上下文记忆 | ✅ 可用 |
| 🛡️ 安全护栏 | Prompt 注入检测、敏感信息脱敏、输出过滤 | ✅ 已接入 |
| 📁 文件管理 | 文本读写、目录浏览、Office 预览（Excel/Word/PPT）、文件监听 | 🔧 已实现 |
| 🔧 Office 工具 | Excel 读写、Word 读写、PPT 读写 | 🔧 已实现 |
| 📊 图表生成 | matplotlib 绑定的可视化工具，base64 图片自动在前端渲染 | 🔧 已实现 |
| 🌐 网页填表 | Playwright 浏览器自动化：浏览、智能填表、内容提取 | ✅ 已验证 |
| 💾 数据管理 | 实验记录/样品/设备的 CRUD，SQLAlchemy ORM 持久化 | ✅ 已接入 ORM |
| 🔌 硬件设备 | 设备列表、实时指标模拟、指令下发（均使用模拟数据） | ⚠️ Mock |
| 🗄️ 数据库 | SQLite + SQLAlchemy + Alembic 迁移 | ✅ 可用 |
| 🔐 用户认证 | JWT 配置就绪，待启用 | 🔌 预留 |

---

## 仓库结构

```
oilchem-agent/
├── backend/                          # 后端 — FastAPI + Python 3.12
│   ├── app/
│   │   ├── agent/                    # Agent 内核
│   │   │   ├── manager.py            #   Agent 管理器（协调 LLM + 工具 + 记忆）
│   │   │   ├── memory/memory.py      #   会话记忆管理
│   │   │   ├── planner/planner.py    #   任务规划器
│   │   │   ├── executor.py           #   计划执行器
│   │   │   └── prompts/prompts.py    #   系统提示词
│   │   ├── api/v1/
│   │   │   └── endpoints/
│   │   │       ├── chat.py           #   对话 API（同步/流式/会话管理）
│   │   │       ├── files.py          #   文件管理 API + WebSocket 监听
│   │   │       ├── web.py            #   网页操作 API（浏览/填表/提取）
│   │   │       ├── hardware.py       #   硬件设备 API
│   │   │       ├── db.py             #   业务数据 CRUD API
│   │   │       ├── llm.py            #   LLM 连通性测试
│   │   │       ├── system.py         #   系统信息
│   │   │       └── health.py         #   健康检查
│   │   ├── core/                     # 配置、日志、安全
│   │   ├── llm/                      # LLM 客户端 + 提供商抽象
│   │   ├── tools/
│   │   │   ├── base.py               #   工具基类
│   │   │   ├── registry.py           #   工具注册表
│   │   │   ├── manager.py            #   工具管理器
│   │   │   └── builtin/
│   │   │       ├── file_tools.py     #     文件系统操作
│   │   │       ├── office_tools.py   #     Office 文档处理
│   │   │       ├── chart_tools.py    #     图表生成
│   │   │       ├── hardware_tools.py #     硬件设备工具
│   │   │       └── web_tools.py      #     浏览器自动化
│   │   ├── services/                 # 后台服务（文件监听）
│   │   ├── database/                 # SQLAlchemy 会话管理
│   │   ├── guardrails/               # 输入/输出护栏 + RBAC
│   │   ├── mcp/                      # MCP 集成框架
│   │   └── schemas/                  # 共享 Pydantic 模型
│   ├── alembic/                      # 数据库迁移
│   ├── scripts/migrate.py            # 迁移管理脚本
│   ├── requirements.txt              # Python 依赖
│   ├── .env.example                  # 环境变量模板
│   └── alembic.ini
├── frontend/                         # 前端 — React + Vite + TypeScript
│   └── src/
│       ├── types/index.ts            #   TypeScript 类型定义
│       ├── services/api.ts           #   API 服务层
│       ├── components/
│       │   ├── ChatWindow.tsx        #     主对话窗口（SSE 流式）
│       │   ├── Sidebar.tsx           #     会话侧边栏
│       │   ├── FileBrowser.tsx      #     文件浏览器 + Office 预览
│       │   ├── HardwarePanel.tsx     #     硬件设备面板
│       │   ├── DatabasePanel.tsx     #     数据管理面板
│       │   ├── WebFormPanel.tsx      #     网页填表面板
│       │   ├── Message.tsx           #     单条消息组件
│       │   ├── MessageList.tsx       #     消息列表
│       │   └── MessageInput.tsx      #     消息输入框
│       ├── App.tsx                   #   根组件 + Tab 导航
│       └── index.css                 #   全局样式
├── docs/                             # 架构文档
│   ├── architecture.md
│   ├── roadmap.md
│   └── api.md
├── CHANGELOG.md
├── README.md
└── LICENSE
```

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端框架** | FastAPI + Uvicorn | Python 3.12 |
| **数据校验** | Pydantic v2 + Pydantic Settings | 2.9.2 |
| **LLM 交互** | HTTPX + 支持 Ollama/OpenAI API | 0.27.2 |
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

在 `backend/.env` 中配置 LLM 提供商：

```env
LLM_PROVIDER=ollama
OPENAI_BASE_URL=http://localhost:11434
OPENAI_API_KEY=
MODEL_NAME=qwen2.5
LLM_TIMEOUT=30.0
LLM_MAX_RETRIES=2
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

使用 Ollama 本地模型：
1. 安装 [Ollama](https://ollama.com)
2. 拉取模型：`ollama pull qwen2.5`
3. 启动 Ollama：`ollama serve`
4. 验证连通性：`GET /api/v1/llm/test`

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

启动时自动执行 Alembic 迁移。手动操作：

```bash
cd backend
python -m scripts.migrate upgrade       # 升级到最新
python -m scripts.migrate downgrade     # 回滚一个版本
python -m scripts.migrate current       # 查看当前版本
python -m scripts.migrate history      # 迁移历史
python -m scripts.migrate create "描述" # 创建新迁移
python -m scripts.migrate drop         # 回退到初始
```

### 认证配置

```env
AUTH_ENABLED=false
JWT_SECRET_KEY=change-me-in-production
JWT_EXPIRE_MINUTES=60
```

### Office 依赖安装

Office 文件处理需要额外的 Python 库：

```bash
pip install openpyxl python-docx python-pptx
```

这些库已在 `requirements.txt` 中声明。

### 网页填表依赖安装

浏览器自动化需要 Playwright：

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

## 工具系统

Agent 内置以下工具，可在对话中自动调用：

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容（支持行范围、二进制检测） |
| `write_file` | 写入文件（覆盖） |
| `append_file` | 追加内容到文件 |
| `list_files` | 列出目录内容（支持递归和 glob） |
| `delete_file` | 删除文件（安全限制） |
| `read_excel` | 读取 Excel 表格数据 |
| `write_excel` | 写入 Excel 表格数据 |
| `read_word` | 提取 Word 文档段落和表格 |
| `read_ppt` | 解析 PPT 幻灯片文本 |
| `browse_webpage` | 浏览网页并提取内容、表单、截图 |
| `fill_webform` | 自动登录并填写网页表单 |
| `extract_webpage_text` | 提取网页文本内容 |
| `draw_chart` | 生成 matplotlib 图表（折线图/柱状图/散点图等） |
| `query_hardware` | 查询硬件设备状态 |
| `send_hardware_command` | 向硬件设备下发指令 |

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

## Git 工作流

- `main` — 稳定版，生产环境
- `develop` — 集成分支
- `feature/*` — 短期功能分支

---

## 相关文档

- [架构设计](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [API 文档](docs/api.md)
- [版本日志](DEVELOPMENT_LOG.md)