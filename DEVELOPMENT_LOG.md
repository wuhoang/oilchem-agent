# OilChem Agent — 开发日志

> 本文档按版本逆序记录每一次功能迭代、缺陷修复和架构变更。
> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
> 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [1.1.0] — 2026-08-15

### Added

- **实验报告自动生成（核心演示点）**
  - 新增 `backend/app/services/report_generator.py`：`generate_report(experiment_id)` 生成 Word 报告（标题 + 实验信息表 + 方案步骤 + 步骤执行表 + 测量数据表 + 审计记录 + 结论段）+ Excel 数据表（多指标分 sheet），文件存 `backend/storage/reports/{experiment_id}/`，幂等复用
  - `Experiment` 加 `report_path` 字段 + Alembic 004 迁移
  - `GET /experiments/{id}/report` 端点返回文件清单
  - orchestrator 实验完成时自动调用 generate_report（失败只记日志）
  - 新增 Agent 工具 `generate_experiment_report`（单工具完成，绕开轮数限制）
  - 前端实验中心"已完成"状态显示"生成/下载报告"按钮

- **追溯视图（运行记录可见化）**
  - `GET /experiments/{id}` 响应加 `audits`（时间正序）+ `protocol_name` + `report_path`
  - 前端详情区加"执行记录"时间线（创建→开始→每步→完成）

- **油化仿真设备**
  - 设备清单从 `hardware_simulation_data.json` 加载：HTHP-01/02（高温高压失水仪）、Rheo-01/02（六速旋转粘度计，600/300/6/3 转读数）、Thick-01/02（稠化仪）
  - 删除 5 台通用假设备；HTHP-01 保留漏失量剧本曲线（7 点插值 30 点）

- **SSE 实验事件（替换轮询）**
  - orchestrator 加 subscribe/unsubscribe/_publish 事件广播；状态变更/步骤变化/measure 落库时推送
  - `GET /api/v1/experiments/events` SSE 端点
  - 前端 EventSource 订阅，替换 3 秒轮询

- **实验员选择**：`GET /experimenters` 端点；前端一键开始弹操作员下拉 + 样品号输入

### Fixed

- **设备不复位（Bug）**：MockDriver 加 `reset()`（`_initial_metrics` 恢复 + `_curve_index.clear()`），`DeviceDriver` 基类加 reset 抽象；orchestrator start 时对实验设备复位——修复第二次实验漏失量直线/温度 180→180 问题
- **BUSY 状态映射**：registry.get_device_info 状态四态透传（idle→online/busy/error/offline）
- **send_command 走统一源**：从 DriverRegistry 取设备，HTHP-01 不再 404
- **created_at 类型**：String→DateTime，batch_alter_table 迁移，种子数据改 datetime 对象
- **超轮数不写 Memory**：chat_with_tools / chat_stream_with_tools 的"已达最大轮数"提示加 skip_memory 标志
- **硬件工具层统一数据源**：`read_hardware` / `send_hardware_command` 从 DriverRegistry 读（不再读旧 `_DEVICES`），`send_command` 走 `driver.send_command`（不再 requests 自回调）；`hardware_collector` 遥测采集也从 DriverRegistry 读——消除硬件 API/工具/采集器三处数据源分裂

### Changed

- 版本号 1.0.0 → 1.1.0
- 工具总数 24 → 25（新增 generate_experiment_report）
- pyproject.toml 补全依赖：openpyxl/python-docx/python-pptx/matplotlib/playwright/watchdog/requests

### 验证

- 连续两次实验：漏失量 30 点（0.5→11.5）、温度 25→180，第二次正常 ✅
- 实验报告：Word + Excel 自动生成，文件真实存在 ✅
- 设备源：6 台油化仿真设备（HTHP/Rheo/Thick 各 2 台）✅
- pytest 2 通过、前端 build 通过 ✅

---

## [1.0.0] — 2026-08-14

### Added

- **实验域完整闭环（跨越式升级，M1-M7 全打通）**

  按 `docs/system_design.md` 顶层设计 + `docs/detailed_design.md` 详细设计落地，实现"选方案 → 一键开始实验 → 设备逐步执行 → 实时数据 → 全程追溯"的演示版自动化实验主线。

  **M1 数据模型**（`models/tables.py` + Alembic 003）
  - 新增 6 表：`experimenters`（实验员）、`protocols`（方案）、`protocol_steps`（步骤模板）、`materials`（物料主数据）、`experiment_steps`（步骤执行实例）、`measurements`（测量数据点）
  - 扩表：`experiments` 加 `operator_id`/`protocol_id`/`sample_code`；`samples` 加 `material_id`
  - 新增 `experiment_audits` 审计表
  - 种子数据真实化：HTHP 高温高压失水仪方案（PROTO-001：升温→恒温→测漏失量）

  **M3 设备驱动层**（`app/hardware/drivers/`）
  - `base.py`：`DeviceDriver` 抽象接口 + `StepResult`/`TelemetryPoint`/`DeviceStatus`
  - `mock.py`：`MockDriver` 剧本引擎——受控升温（按爬坡速率）、恒温计时、漏失量曲线（剧本曲线推进）
  - `registry.py`：`DriverRegistry` 设备占用管理（冲突抛 BusyError）

  **M2 编排引擎**（`app/services/orchestrator.py`）
  - 实验状态机：草稿→待执行→执行中→完成/异常/中止
  - 步骤展开：start 时读 protocol_steps 实例化为 experiment_steps
  - 主循环：逐步骤执行、设备占用、异常冻结、measurement_count 判据采多点
  - 异常恢复：retry_step/skip_step/abort，现场不丢失
  - 审计：create/status/step_succeed/step_fail 事件落库

  **M5 交互层**
  - `experiments.py` 端点：GET/POST protocols、experiments CRUD、progress、measurements、dashboard
  - `experiment_tools.py`：5 个实验域 Agent 工具（list_protocols/create_experiment/start_experiment/query_progress/query_result）

  **M6 数据采集**：measure 步骤按 complete_criteria（measurement_count）循环采 N 点，写 measurements

  **M7 审计追溯**：`ExperimentAudit` + Orchestrator 关键动作审计

  **前端「实验中心」**（`ExperimentCenter.tsx`）
  - 三视角合一：方案库（左）/ 实验列表+看板统计（中）/ 实验详情+数据（右）
  - 一键开始实验、3 秒轮询进度、测量数据展示

### Fixed

- Alembic 003 迁移在 fresh 部署下 `ALTER TABLE experiments` 报 no such table：001 未建 experiments/samples/devices（历史上由 create_all 补建），003 改为先幂等补建基础表再 alter
- measure 步骤只采 1 个点：measurement_count 判据未实现，改为 Orchestrator 层循环采 N 点
- 漏失量全 0：MockDriver 加剧本曲线机制，HTHP 漏失量按 7 点曲线递增产出

### Changed

- 版本号跳跃 0.17.0 → 1.0.0（演示版主链路闭环）
- 工具总数 19 → 24（新增 5 个实验域工具）

### 验证

- 端到端：创建实验 → 启动 → 升温→恒温→测量 → 状态"已完成"，7 个漏失量数据点正确（2.5→12.8 ml）✅
- 审计事件 6 条（create/status ×2/step_succeed ×3）✅
- pytest 2 个 smoke test 通过 ✅
- 前端 `npm run build` 成功（372KB）✅

---

## [0.17.0] — 2026-08-13

### Added

- **Agent 工具调用迁移到原生 function calling（核心重构）**
  - 背景：旧链路是 Planner 让 LLM 手写 JSON 计划 → 正则容错解析 → Executor 执行 → 字符串模板传数据，痛点：参数写错一步就废、静默降级成纯聊天、步骤间字段名写错断链、一个任务 5-8 次 LLM 调用
  - 新链路：模型直接输出结构化 `tool_calls`，工具结果以 `role="tool"` 消息回传，模型自主决定继续/重试/给最终回答
  - `ToolManager.list_tools_schema()`：工具元数据 → OpenAI tools 协议格式
  - `AgentManager.chat_with_tools()`：同步主入口，`max_iterations=8` 防死循环，工具往返不写 Memory（避免污染多轮对话），图片数据走 SSE chart 事件不进 LLM 上下文
  - `AgentManager.chat_stream_with_tools()`：流式 SSE 主入口，工具决策用非流式（规避流式 tool_calls 增量解析），最终回复用流式（打字机效果）
  - `ChatMessage` 增加 `tool_call_id`/`tool_calls` 字段；`LLMClient.chat()` 透传 `tools` 参数
  - `provider.py`：消息序列化支持 `role="tool"` 和 assistant `tool_calls`；`_parse_response` 透传 `tool_calls`（Ollama 版同步适配）
- **系统顶层设计文档（`docs/system_design.md`）**
  - 定位：系统是"实验管理系统（LIMS）与实验硬件设备之间的中间层"，核心价值为人-机-料-数据全程关联可追溯；交互层（Web + Agent）只是顺带门面
  - 目标分两层：**演示版**（PoC，向管理者展示"选方案→一键实验→设备逐步执行→实时数据→全程追溯"的自动化主线，设备/管理系统均为 Mock 但数据模型与流程为真实设计）；**生产版**（对接真实 LIMS 拉取实验设计/回传结果，真实设备协议 RS232/USB/GPIB，自动实验无人值守闭环，LLM 不进执行主链路）
  - 模块划分 M1-M7：M1 数据模型（含 materials 物料主数据与 samples 样品实例的区分）、M2 编排引擎（任务状态机 + ExperimentStep 步骤模型 + 异常冻结/重试/跳步/中止恢复策略）、M3 设备驱动抽象（同步 execute_step + 遥测独立轮询的接口契约，MockDriver 剧本引擎/Serial/Http/Gpib 驱动可互换）、M4 管理系统对接（演示版 Mock 源占位）、M5 交互层（看板/工作台/追溯三视角 + 实验域 Agent 工具，现有 5 个 Tab 保留为辅助工作台）、M6 数据采集（实验级 measurements + 复用 telemetry）、M7 审计追溯
  - 构建顺序按依赖而非时间排期：M1 → M3 → M2 → M6 → M5 → M7 → M4（M3 不依赖 M2 可独立先行验证）

### Fixed

- **工具 parameters 混合格式导致 400（关键 bug）**：`file_tools.py` 的 5 个工具用标准 JSON Schema（`type:object`+`properties`），其余 14 个工具用扁平字典（`{"device_id": {...}}`）。扁平格式被 DeepSeek function calling 判非法返回 400。修复：`_normalize_schema()` 把扁平字典包装成标准格式（required=[]）

### Changed

- **前端"思考过程"改为"实时工具调用流"**：不再有预生成计划清单，改为动态追加工具调用项（`ToolCallInfo.step_id` → `call_index`）
- **流式事件序列**：移除 planning 事件，改为 `thinking → tools(start/complete) → chunk → done`
- **旧链路保留但主调用方切换**：`planner.py`/`executor.py` 文件保留（暂不删除，稳定后清理），`chat()`/`chat_stream()`/`plan()`/`execute_step()` 方法保留向后兼容，但 `/chat` 和 `/chat/stream` 端点已切到 function calling 新方法

### 验证

- 纯对话（"你好"）→ 无 tool_calls，直接文本回复 ✅
- 历史趋势（"rct-01 过去60分钟温度趋势"）→ 正确调用 `query_hardware_history` ✅
- 文件任务（"读取 hardware_info 目录的 json"）→ 正确调用 `list_files` + `read_file` ✅
- SSE 事件序列 → `thinking → tools(start) → tools(complete) → chunk × N → done` ✅
- `pytest` 2 个 smoke test 通过 ✅
- 前端 `tsc -b` 通过 ✅

---

## [0.16.3] — 2026-08-13

### Fixed

- **消除"项目用本地小模型 qwen2.5"的误导**
  - 问题：实际使用 DeepSeek（`deepseek-chat`），但 CLAUDE.md / README / api.md / PROJECT_STATUS.md 多处把 qwen2.5、Ollama 当作默认描述，导致审查 Agent 误判"模型能力不足"
  - `CLAUDE.md` 明确标注实际 LLM 为 DeepSeek，Ollama 仅为预留 Provider；"关键已知问题"改为说明当前 DeepSeek 表现良好
  - `config.py` 默认值从 `ollama + qwen2.5` 改为 `openai + deepseek-chat`（运行仍以 `.env` 为准）
  - README LLM 配置章节重写，DeepSeek 放首位、Ollama 标注为备用方案
  - api.md / PROJECT_STATUS.md 的示例与描述同步为 DeepSeek

---

## [0.16.2] — 2026-08-13

### Fixed

- **移除 3 处硬编码本地路径**（仓库公开后检查发现）
  - `frontend/src/components/FileBrowser.tsx`：默认目录从 `H:\trae-project\oilchem-agent` 改为空字符串
  - `backend/app/tools/builtin/file_tools.py`：`_resolve_path()` 对空路径回退到项目根目录，通过 `Path(__file__).resolve().parents[4]` 代码相对定位（不依赖启动工作目录、不写死本机路径），效果与前端原默认目录完全一致
  - `backend/app/agent/planner/planner.py`：系统提示词中示例路径改为通用写法 `C:\Users\<用户名>\<项目名>`
  - `docs/file_access_scope.md`：改为描述 `FILE_ALLOWED_PATHS` 配置而非写死具体目录
- **版本号全量统一到 0.16.2**：`.env.example`、CLAUDE.md、DEVELOPMENT.md、README.md 之前停留在 0.15.0/0.16.0 未同步，本次与代码 8 处版本号（config/constants/pyproject/.env/package.json/package-lock/App/Sidebar/api.md）一并统一

---

## [0.16.1] — 2026-08-10

### Changed

- **系统提示词新增「硬件设备使用指南」**
  - 列出 5 台已接入设备及其指标（rct-01 加氢反应器/温度压力液位、gc-01 气相色谱仪/柱温载气压力、bal-01 分析天平/重量、ph-01 pH计/pH温度、pump-01 蠕动泵/流速）
  - 明确工具分工：`read_hardware` = 实时快照（问"现在多少"）；`query_hardware_history` = 历史趋势（问"过去X分钟"）
  - 给出画趋势图标准步骤：query_hardware_history → 拿 timestamps/values → 传给 plot_chart
- **`read_hardware` 工具描述优化**
  - 强调「实时」定位，明确历史查询请用 `query_hardware_history`
  - device_id 参数补充每个设备的中文名
- **`query_hardware_history` 工具描述优化**
  - 强调「历史趋势」定位，明确实时查询请用 `read_hardware`
  - start_time 默认值说明更清晰

### 效果

实测对比（修复前后）：
- 问"现在温度多少" → 修复前可能误用历史工具，修复后正确用 `read_hardware` 返回实时值 184.486°C
- 问"过去30分钟趋势" → 修复后正确用 `query_hardware_history` 返回时间序列并画折线图

这是解决"模型对 Agent 不了解、有割裂感"的关键一步：让模型知道有哪些设备、每个工具管什么。

---

## [0.16.0] — 2026-08-10

### Added

- **设备遥测历史采集系统**
  - 新增 `backend/app/services/hardware_collector.py`：`HardwareCollectorService`
    - 后台异步轮询循环（`asyncio.create_task`），默认 10 秒间隔
    - 每次从 Mock 硬件源读取设备指标，批量写入 `device_telemetry_history` 表
    - 自动清理超期记录（按 `HARDWARE_HISTORY_RETENTION_MINUTES` 保留窗口，默认 1440 分钟 = 24 小时，每次采集后执行）
    - `start()` / `stop()` 生命周期方法，`get_hardware_collector()` 全局单例
    - 遵循 `FileWatcherService` 模式
  - 新增 ORM 模型 `DeviceTelemetryHistory` (`models/tables.py`)
    - `id` (Integer PK)、`device_id` (String(64), index)、`metric_name` (String(64))
    - `metric_value` (Float)、`unit` (String(32))、`timestamp` (DateTime(timezone=True), index)
  - 新增 Alembic 迁移 `002_device_telemetry_history.py`
  - 新增 Agent 工具 `query_hardware_history` (第 19 个已注册工具)
    - 参数：`device_id`、`metric_name`（可选）、`start_time`（相对分钟数或 ISO）、`end_time`（可选 ISO）
    - 降采样：超过 100 个点时均匀抽取
    - 返回 timestamps + values + plot_hint，可直接喂给 `plot_chart`
  - 新增配置项：`HARDWARE_COLLECT_INTERVAL` (10s)、`HARDWARE_HISTORY_RETENTION_MINUTES` (1440min)
  - `main.py` lifespan 集成：启停硬件采集器

- **Executor 上下文引用增强**
  - `_resolve_tool_args` 支持点路径：`{step_N_result.字段名}` 提取 dict 子字段（保留原始类型）
  - Planner prompt 新增步骤间数据传递规则，教 LLM 用模板引用而非自然语言占位符

- **chart_tools 数据校验**
  - y_data 类型检查：非 list 给出明确错误提示（含 `{step_N_result.字段名}` 引用指导）
  - y_data 内容校验：非数值元素给出具体错误

### Fixed

- **`plot_chart` 缩进 bug（关键）**：数据校验 `return` 后生成代码全部在 except 块内成为死代码，ToolManager 收到 None 报 `'NoneType' object has no attribute 'success'`
- **Executor 参数覆盖**：移除 `tool_args.update(step.tool_args)`，避免覆盖上下文解析结果
- **Planner f-string 花括号**：`{step_N_result}` 字面值在 f-string 中未转义导致格式化错误，修复为 `{{step_N_result}}`

### Changed

- 版本号 0.15.1 → 0.16.0
- `config.py` 新增 `hardware_collect_interval` / `hardware_history_retention_minutes`
- `main.py` lifespan 新增硬件采集器启停

---

## [0.15.1] — 2026-08-10

### Added

- **全局错误提示组件** (`frontend/src/components/ErrorToast.tsx`)
  - 通过 `notifyError(message)` 触发，`window.dispatchEvent(new CustomEvent("oilchem:error"))`
  - 在页面顶部居中显示红色错误提示条，6 秒自动消失，支持手动关闭
  - 带滑入动画，多错误可堆叠
  - 挂载在 `App.tsx` 根部，全局生效
- **错误提示接线**
  - `ChatWindow.tsx`：SSE `error` 事件、请求失败（网络错误/后端宕机）→ `notifyError`
  - `DatabasePanel.tsx`：新增/编辑/删除失败 → `notifyError`，替换原来的 `alert()` 弹窗
- **前端首次生产构建** (`npm run build`)：此前从未跑过完整构建，本次首次成功

### Fixed

- `FileBrowser.tsx`：Word 预览 `tables`、PPT 预览 `slides`/`text_content`/`tables`/`notes` 的隐式 `any` 类型补全
- `Message.tsx`：删除未使用的 `ChartData` 导入和 `match` 变量

### Changed

- 版本号 0.15.0 → 0.15.1

---

## [0.15.0] — 2026-08-10

### Added

- **Guardrails 接入对话端点**
  - `POST /api/v1/chat`：用户消息经 `InputGuardrail.check()` 检测注入攻击 + 脱敏，LLM 回复经 `OutputGuardrail.check()` 过滤
  - `POST /api/v1/chat/stream`：输入检查同上，输出在流式完成后做审计日志
  - Prompt 注入检测返回 400，正常对话不受影响

- **DB 端点接入 ORM**
  - 新增 `Experiment` / `Sample` / `Device` 三个 ORM 模型（`models/tables.py`），含种子数据常量
  - `db.py` 全面重写：删除内存 `_SEED_DATA`，改用 `get_db()` 依赖注入 + `AsyncSession` + `select()` 真实查询
  - `init_db()` 架构调整：Alembic → create_all 补建新表 → 种子数据自动填充（幂等），三阶段均执行不再早 return
  - 种子数据：5 实验 + 4 样品 + 5 设备，仅空表时插入

- **前端数据管理面板重写** (`DatabasePanel.tsx`)
  - 启动时从 `/api/v1/db/tables` 加载表列表，切表时从 `/api/v1/db/{table}/query` 加载行数据
  - 新增：内联表单，填完保存 → `POST /db/{table}/insert` → 即时刷新
  - 编辑：点击转为输入框，改完保存 → `POST /db/{table}/update`
  - 删除：确认弹窗 → `DELETE /db/{table}/delete`
  - 导出 CSV：真实导出当前表数据，不再弹 alert
  - 错误状态栏：后端异常时显示红色错误信息

- **前端 API 层扩展** (`services/api.ts`)
  - 新增 `fetchDbTables` / `queryDbTable` / `insertDbRow` / `updateDbRow` / `deleteDbRow`

- **结构化日志增强**
  - chat 端点：guardrail 阻断 warning、对话成功 info（含 session/plan/time）、流式审计 warning
  - DB 端点：查询 info、插入 info、更新 info、删除 warning

### Fixed

- **`init_db()` Alembic 早 return Bug**：Alembic 迁移成功后直接 `return`，导致新增的 Experiment/Sample/Device 表从未创建、种子数据从未填充。修复为 Alembic → create_all → seed 三阶段顺序执行
- **前端数据面板所有操作为 alert("接口预留")**：现已全部接入后端 API

### Changed

- 版本号 0.14.1 → 0.15.0（8 处统一）
- README.md：功能表诚实标注，删除不存在章节，修正前端功能描述
- PROJECT_STATUS.md：全面更新 DB/Guardrails 状态，新增 v0.15.0 变更记录

---

## [0.14.1] — 2026-08-08

### Added

- **一键启动器**
  - 新增 `start.py`：Python 启动器（跨平台）
    - 自动检测 Python 3.12+ 和 Node.js 22+ 环境
    - 自动创建后端虚拟环境 `backend/.venv`
    - 自动安装后端 pip 依赖 + 前端 npm 依赖
    - 自动从 `.env.example` 生成 `.env` 配置文件
    - 同时启动后端（端口 8000）和前端（端口 5173）
    - 等待服务就绪后自动打开浏览器
    - 端口占用检测，避免重复启动
  - 新增 `start.bat`：Windows 双击启动入口
  - 新增 `stop.bat`：Windows 一键停止所有服务
  - 更新 `README.md`：新增一键启动章节

---

## [0.14.0] — 2026-08-08

### Added

- **网页填表模块**
  - 新增 `backend/app/tools/builtin/web_tools.py`：浏览器自动化工具
    - `browse_webpage`：浏览网页，返回页面内容、表单元素和截图
    - `fill_webform`：自动登录 + 填写表单 + 提交（支持用户名密码认证）
    - `extract_webpage_text`：提取网页文本内容（支持 CSS 选择器过滤）
  - 新增 `backend/app/api/v1/endpoints/web.py`：网页操作 REST API
    - `POST /api/v1/web/browse`：浏览网页
    - `POST /api/v1/web/fill-form`：自动填表
    - `POST /api/v1/web/extract-text`：文本提取
  - 新增 `frontend/src/components/WebFormPanel.tsx`：网页填表独立面板
    - URL 输入框 + 用户名/密码字段
    - 动态表单字段编辑器（键值对映射）
    - 一键自动登录填表执行
  - 更新 `frontend/src/App.tsx`：新增「网页填表」Tab（紫色）

- **会话管理优化**
  - 会话标题自动生成：基于首条消息前 20 字自动生成会话标题
  - UUID 简化显示：侧边栏截取 UUID 后 8 位作为会话标识
  - 会话按 `updated_at` 倒序排列
  - 消息数实时更新：对话结束后自动刷新侧边栏

### Fixed

- **会话列表不刷新**：已发送消息的会话不触发侧边栏刷新
  - 原因：仅在新建会话时刷新，已有会话消息增加不触发刷新
  - 修复：`ChatWindow` 消息完成时调用 `onMessageComplete`，触发 `sidebarRefresh` 状态更新
- **LLM 不知道图表已生成**：Agent 回复"没画出来"但前端实际已显示
  - 原因：工具结果包含完整 base64 图片数据，LLM 无法解析
  - 修复：`_sanitize_tool_output` 检测图表输出，替换为可读性描述
- **新建会话异常**：始终只显示固定数量的对话
  - 原因：新建会话与刷新时机不对齐
  - 修复：统一刷新时机，确保新建后立即出现在列表中
- **会话 ID 显示乱码**：完整 UUID 直接展示
  - 修复：优先显示标题，备选截取后 8 位
- **文件预览路径错误**：Office 文件预览路径解析异常
  - 修复：新增 `resolve_workspace_path()` 统一路径解析

### Changed

- 更新 `backend/app/agent/manager.py`：`_sanitize_tool_output` 过滤图表 base64，`_build_tool_summary` 增加工具摘要构建
- 更新 `backend/app/api/v1/endpoints/chat.py`：`SessionResponse` 新增 `title` / `created_at` / `updated_at` 字段
- 更新 `frontend/src/components/Sidebar.tsx`：标题 + UUID 简化显示，消息数实时更新
- 更新 `frontend/src/components/ChatWindow.tsx`：消息完成回调
- 更新 `frontend/src/App.tsx`：5-Tab 布局（对话/文件/硬件/数据/网页填表）

---

## [0.13.0] — 2026-08-08

### Added

- **数据管理模块**
  - 新增 `backend/app/api/v1/endpoints/db.py`：业务数据 CRUD API
    - `GET /api/v1/db/tables`：列出业务表（experiments / samples / devices / users）
    - `POST /api/v1/db/{table}/query`：查询表数据（支持关键字搜索、分页）
    - `POST /api/v1/db/{table}/insert`：插入一行数据
    - `POST /api/v1/db/{table}/update`：更新一行数据
    - `DELETE /api/v1/db/{table}/delete`：删除一行数据
  - 新增 `frontend/src/components/DatabasePanel.tsx`：数据管理面板
    - 表切换 Tab
    - 表格视图 + 关键字搜索
    - 新增/编辑/删除行操作
    - 预置演示数据（柴油加氢脱硫评价、催化裂化催化剂筛选等实验记录）

### Changed

- 更新 `backend/app/api/v1/router.py`：注册 `db` 路由
- 更新 `frontend/src/App.tsx`：新增「数据管理」Tab（紫色）

---

## [0.12.0] — 2026-08-08

### Added

- **硬件设备模块**
  - 新增 `backend/app/tools/builtin/hardware_tools.py`：硬件工具
    - `query_hardware`：查询设备状态、实时指标
    - `send_hardware_command`：向设备下发指令（start/stop/reset/calibrate）
  - 新增 `backend/app/api/v1/endpoints/hardware.py`：硬件设备 REST API
    - `GET /api/v1/hardware/devices`：列出所有设备（含实时指标，支持随机漂移模拟）
    - `GET /api/v1/hardware/devices/{id}`：获取单个设备详情
    - `POST /api/v1/hardware/devices/{id}/command`：下发设备指令
    - 预置设备：加氢反应器 R-101、气相色谱仪 GC-2030、分析天平 XS205、pH 计 FE28、蠕动泵 RP-100
  - 新增 `frontend/src/components/HardwarePanel.tsx`：硬件设备面板
    - 设备卡片列表（状态在线/离线指示）
    - 实时指标监控（温度/压力/液位等，带 min/max 范围指示器）
    - 指令下发（start/stop/calibrate 按钮）
    - 指标随机漂移模拟实时数据

### Changed

- 更新 `backend/app/api/v1/router.py`：注册 `hardware` 路由
- 更新 `frontend/src/App.tsx`：新增「硬件设备」Tab（绿色）

---

## [0.11.0] — 2026-08-08

### Added

- **Office 文档处理模块**
  - 新增 `backend/app/tools/builtin/office_tools.py`：Office 工具
    - `read_excel`：读取 Excel 文件所有 Sheet 数据，返回结构化 JSON
    - `write_excel`：写入数据到 Excel 文件（支持多 Sheet）
    - `read_word`：提取 Word 文档所有段落和表格内容
    - `read_ppt`：解析 PPT 幻灯片文本内容
    - `resolve_workspace_path`：统一路径解析（支持工作区根目录 + 绝对路径）
  - 新增 `backend/app/api/v1/endpoints/files.py`：文件预览 API
    - `POST /api/v1/files/preview`：预览文件（根据扩展名路由到不同解析器）
    - Excel 预览：返回所有 Sheet、表头、行数据、行数统计
    - Word 预览：返回段落列表、表格内容
    - PPT 预览：返回幻灯片列表、每页文本内容
  - 新增 `frontend/src/components/FileBrowser.tsx`：文件浏览器 + Office 预览
    - ExcelPreview 组件：表格化展示多 Sheet 数据
    - WordPreview 组件：文档结构展示（段落 + 表格）
    - PPPreview 组件：幻灯片导航
    - 文本文件预览：代码高亮显示
  - 新增 `backend/app/tools/builtin/chart_tools.py`：图表生成工具
    - `draw_chart`：基于 matplotlib 生成折线图/柱状图/散点图/饼图/面积图
    - 返回 base64 图片数据，前端自动渲染

- **依赖更新**
  - `requirements.txt` 新增：
    - `openpyxl==3.1.5`（Excel 读写）
    - `python-docx==1.1.2`（Word 读取）
    - `python-pptx==1.0.2`（PPT 读取）
    - `matplotlib==3.10.0`（图表生成）

### Changed

- 更新 `backend/app/tools/__init__.py`：自动导入 office_tools / chart_tools / hardware_tools / web_tools
- 更新 `frontend/src/App.tsx`：新增「文件管理」Tab（琥珀色）
- 更新 `README.md`：新增 Office 依赖安装、文件预览说明

---

## [0.10.0] — 2026-08-08

### Added

- **Step 9: Frontend Chat UI** ✅
  - 新增 `frontend/src/types/index.ts`：TypeScript 类型定义
    - ChatMessage / ChatRequest / ChatResponse
    - SessionInfo / StreamEvent / LLMInfo / ToolInfo
  - 新增 `frontend/src/services/api.ts`：API 服务层
    - 对话接口：sendChatMessage / sendChatMessageStream（SSE 流式）
    - 会话管理：listSessions / getSession / deleteSession
    - LLM：testLLM / getLLMInfo
    - 文件：readFile / writeFile / listTools
    - 健康检查：healthCheck
  - 新增 `frontend/src/components/Message.tsx`：单条消息组件
    - 区分用户/AI 角色样式
    - 流式打字指示器
    - 时间戳显示
  - 新增 `frontend/src/components/MessageList.tsx`：消息列表
    - 自动滚动到底部
    - 空状态 + 快速建议按钮
  - 新增 `frontend/src/components/MessageInput.tsx`：消息输入框
    - 多行输入、Enter 发送、Shift+Enter 换行
  - 新增 `frontend/src/components/Sidebar.tsx`：会话侧边栏
    - 会话列表、切换、删除
    - 新建会话按钮
  - 新增 `frontend/src/components/ChatWindow.tsx`：主对话窗口
    - SSE 流式接收 + 打字机效果
    - 停止生成、加载状态
  - 更新 `frontend/src/App.tsx`：根组件布局
  - 更新 `frontend/src/index.css`：全局样式 + 滚动条美化

---

## [0.9.0] — 2026-08-08

### Added

- **Step 8: Alembic Database Migration** ✅
  - 新增 `backend/alembic.ini`：Alembic 主配置文件
  - 新增 `backend/alembic/env.py`：Alembic 环境配置
    - 自动从 `settings` 获取数据库 URL
    - 异步 URL → 同步 URL 转换（aiosqlite → sqlite）
    - SQLite batch 模式支持
    - 离线/在线双模式迁移
  - 新增 `backend/alembic/script.py.mako`：迁移脚本模板
  - 新增 `backend/alembic/versions/001_initial_tables.py`：初始迁移脚本
    - 创建 users / sessions / messages / tool_audits / knowledge 五张表
    - 包含索引、外键、唯一约束
  - 新增 `backend/scripts/migrate.py`：迁移管理脚本
    - `upgrade`：升级到最新
    - `downgrade`：回滚一个版本
    - `current` / `history`：版本信息查询
    - `create`：自动生成新迁移
    - `drop`：回退到 base
  - 更新 `app/database/session.py`：`init_db()` 优先使用 Alembic 迁移，失败回退 `create_all`

### Changed

- 更新 `scripts/README.md`：新增迁移命令使用说明
- 更新 `README.md`：新增数据库迁移章节

---

## [0.8.0] — 2026-08-08

### Added

- **Step 3: Agent Kernel (Planner + Executor + Memory + Manager + Prompts)** ✅
  - 新增 `app/agent/memory/memory.py`：会话内存管理
    - `MemoryEntry` / `ConversationMemory` 数据模型
    - `MemoryManager`：会话管理、消息存储、上下文获取、自动摘要压缩
    - 长期知识存储与关键词搜索
  - 新增 `app/agent/planner/planner.py`：任务规划器
    - `PlanStep` / `Plan` 数据模型
    - `Planner`：LLM 驱动的任务拆解，支持澄清检测
  - 新增 `app/agent/executor.py`：计划执行器
    - `StepResult` / `ExecutionResult` 数据模型
    - `Executor`：逐步执行、工具调用、步骤间结果传递、LLM 反思决策
  - 新增 `app/agent/manager.py`：Agent 管理器
    - `AgentManager`：协调 LLM + Planner + Executor + Memory + Tools
    - `AgentChatRequest` / `AgentChatResponse` 数据模型
    - 会话管理 API（列出/删除会话）
  - 新增 `app/agent/prompts/prompts.py`：系统提示词管理
    - 默认系统提示词 + 石油化工领域专用提示词
    - `get_system_prompt()` / `get_planning_prompt_template()`

- **Step 4: Chat API** ✅
  - 新增 `app/api/v1/endpoints/chat.py`：Agent 对话端点
    - `POST /api/v1/chat`：同步对话
    - `POST /api/v1/chat/stream`：SSE 流式对话
    - `GET /api/v1/chat/sessions`：列出会话
    - `GET /api/v1/chat/sessions/{id}`：获取会话详情
    - `DELETE /api/v1/chat/sessions/{id}`：删除会话

- **Step 5: Database + ORM Models** ✅
  - 新增 `app/models/tables.py`：ORM 模型
    - `User` / `Session` / `Message` / `ToolAudit` / `Knowledge` 表
  - 更新 `app/database/base.py`：SQLAlchemy DeclarativeBase
  - 更新 `app/database/session.py`：异步引擎 + 会话工厂 + FastAPI 依赖
  - 新增 `aiosqlite==0.20.0` 依赖
  - 更新 `config.py`：新增 database_url / db_echo 配置

- **Step 6: Auth + Permission** ✅
  - 新增 `app/guardrails/permission.py`：RBAC 权限控制
    - `Role` 枚举（admin / user / viewer）
    - `PermissionChecker`：权限检查、角色权限管理
  - 更新 `config.py`：新增 auth_enabled / jwt_secret_key / jwt_expire_minutes

- **Step 7: Guardrails + MCP Framework** ✅
  - 新增 `app/guardrails/input_guard.py`：输入护栏
    - Prompt 注入检测、敏感信息脱敏、输入长度限制
  - 新增 `app/guardrails/output_guard.py`：输出护栏
    - 有害内容过滤、敏感信息脱敏
  - 新增 `app/mcp/client.py`：MCP 集成框架
    - `MCPClient`：连接 MCP Server、调用工具
    - `MCPManager`：管理多个 MCP Server 实例

### Changed

- 更新 `app/main.py`：集成数据库初始化/关闭到 FastAPI 生命周期
- 更新 `app/api/v1/router.py`：注册 chat 路由
- 更新 `README.md`：反映完整进度、新增 API 路由表
- 更新 `docs/api.md`：新增 Chat API 端点文档
- 更新 `docs/architecture.md`：反映 Agent 内核架构
- 更新 `docs/roadmap.md`：Step 3-7 标记为完成
- 更新 `.env.example`：新增数据库、认证配置项

---

## [0.3.0] — 2026-08-08

### Added

- **Step 2: Tools Registry + Builtin File Tools + File Watcher** ✅
  - 新增 `app/tools/base.py`：工具基类
    - `ToolMetadata`（工具元数据模型）
    - `ToolResult`（工具执行结果模型）
    - `BaseTool`（抽象基类，定义 execute 接口）
  - 新增 `app/tools/registry.py`：工具注册表
    - `@register_tool` 装饰器注册工具
    - `get_tool_class()` / `list_tools()` / `get_all_tool_classes()` 等查询方法
  - 新增 `app/tools/manager.py`：工具管理器
    - `ToolManager` 类：统一工具入口，支持查找、执行、错误处理
  - 新增 `app/tools/builtin/file_tools.py`：文件系统工具
    - `read_file`：读取文件内容（支持行范围、二进制检测）
    - `write_file`：写入文件（覆盖）
    - `append_file`：追加内容到文件
    - `list_files`：列出目录内容（支持递归和 glob 过滤）
    - `delete_file`：删除文件（安全限制，不支持目录）
    - 路径安全检查：白名单机制 + 路径解析
  - 新增 `app/services/file_watcher.py`：文件监听服务
    - `FileChangeHandler`：watchdog 事件处理器
    - `DebouncedEventProcessor`：防抖事件合并
    - `FileWatcherService`：服务生命周期管理 + 发布订阅
    - `get_file_watcher()`：全局单例
  - 新增 `app/api/v1/endpoints/files.py`：文件管理 API
    - REST 端点：read / write / append / list / delete / tools
    - 监听管理：watch/start / watch/stop
    - WebSocket：`/ws/files/events` 实时推送文件变化事件
  - 更新 `app/main.py`：集成文件监听服务到 FastAPI 生命周期
  - 更新 `app/tools/__init__.py`：自动导入内置工具完成注册
  - 更新 `requirements.txt`：新增 `watchdog==3.0.0`

### Changed

- 更新 `README.md`：反映 Step 2 进度、新增文件系统配置和监听使用说明
- 更新 `docs/api.md`：新增文件管理端点文档
- 更新 `docs/architecture.md`：反映工具系统和文件监听架构
- 更新 `docs/roadmap.md`：Step 2 标记为完成

---

## [0.2.0] — 2026-08-08

### Added

- **Step 1: LLM Client + Config Wiring** ✅
  - 新增 `app/llm/schemas.py`：LLM 交互数据模型
    - `MessageRole` 枚举、`ChatMessage`、`ChatCompletionRequest`
    - `Usage`、`ChatCompletionChoice`、`ChatCompletionResponse`
    - `StreamDelta`、`StreamChunk`（流式响应支持）
    - `ProviderConfig`（提供商配置模型）
  - 新增 `app/llm/provider.py`：LLM 提供商抽象层
    - `BaseProvider` 抽象基类（统一 chat / stream_chat 接口）
    - `OpenAIProvider`（OpenAI 兼容 API，SSE 流式解析）
    - `OllamaProvider`（本地 Ollama 部署，NDJSON 流式解析）
    - 提供商注册表 + `@register_provider` 装饰器
  - 新增 `app/llm/client.py`：LLM 客户端
    - `LLMClient` 类：重试 + 指数退避、日志、错误处理
    - `chat()` / `stream_chat()` / `test_connection()` 方法
    - `from_settings()` 工厂方法
  - 新增 `app/llm/__init__.py`：模块统一导出
  - 新增 `app/api/v1/endpoints/llm.py`：LLM 管理端点
    - `GET /api/v1/llm/test`：连通性测试
    - `GET /api/v1/llm/info`：配置信息查询
  - 扩展 `app/core/config.py`：新增 LLM + 文件系统配置项
    - `llm_provider`、`llm_timeout`、`llm_max_retries`
    - `llm_temperature`、`llm_max_tokens`
    - `file_allowed_paths`、`file_watch_paths`、`file_debounce_ms`
  - 更新 `.env.example`：同步所有新增配置项

### Changed

- 更新 `README.md`：反映 Step 1 进度、新增 LLM 配置说明、API 路由表
- 更新 `docs/api.md`：新增 LLM 管理端点文档
- 更新 `docs/architecture.md`：反映 LLM 模块架构
- 更新 `docs/roadmap.md`：Step 1 标记为完成

---

## [0.1.0] — 2026-08-08

### Added

- **Step 0: Project Bootstrap**
  - 后端骨架：FastAPI + Uvicorn + Pydantic + Loguru
  - 前端骨架：React + Vite + TypeScript + TailwindCSS
  - Docker 部署配置：backend / frontend / nginx
  - 核心模块占位：agent / llm / tools / database / guardrails / mcp
  - 基础设施：健康检查、根路由、CORS、日志系统
  - 文档：README.md / docs/architecture.md / docs/roadmap.md / docs/api.md
  - 版本日志：DEVELOPMENT_LOG.md
