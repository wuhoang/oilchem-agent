# Changelog

All notable changes to OilChem Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.3] - 2026-08-16

### Fixed

- **聊天主链路崩溃**：get_system_prompt() 用 str.format() 填充动态设备表，提示词正文中的 JSON 示例大括号（如 {"字段名": "值"}）被误解析为占位符导致 KeyError，聊天必崩；改用 str.replace() 只替换 {device_table} 占位符
- **审核人默认值混用**：前端未选审核人时把实验员 ID（如 OP-001，字符串）传给 reviewer_id（int）导致 422；审核人下拉默认选中第一个审核账号，新增 Reviewer 类型（数字 ID）与实验员类型（字符串 ID）区分
- **中止按钮无状态限制**：前端「中止实验」按钮对任何状态显示、后端 abort 无校验，「已完成」实验可被改成「中止」；前端仅「执行中」显示按钮，后端 abort 校验状态
- **start 可重复展开步骤**：对已完成实验再调 start 会重复插入实验步骤并重跑；start 增加状态校验，仅「草稿」/「待执行」可启动
- **retry/skip/abort/start 端点缺异常处理**：orchestrator 抛 ValueError/KeyError 时直接 500；端点补捕获并映射 400/404

## [1.3.2] - 2026-08-16

### Fixed

- **系统提示词设备表过时**：替换为实际的 6 台油化仿真设备（HTHP-01/02、Rheo-01/02、Thick-01/02），含型号和真实指标名；领域知识从石油炼制改为钻井液测试（HTHP 失水、流变性、稠化时间）
- **编排引擎 abort 释放全部设备**：改为只释放当前实验占用的设备，不影响并发实验
- **编排引擎 retry_step/skip_step 缺防重入**：加互斥保护，防止用户双击导致多个 `_run_loop` 并行
- **步骤超时不执行**：用 `asyncio.wait_for()` 包裹 `_execute_step`，超时后返回失败而非永远挂着
- **cancel 后实验卡在「执行中」**：`CancelledError` 处理器现在正确设置状态为「中止」

### Added

- **登录限流**：`POST /auth/login` 加内存限流（5 次/5 分钟/IP），防暴力破解，进程重启自动清零

## [1.3.1] - 2026-08-16

### Changed

- 删除 `mock.py` 死代码 `load_hthp_behavior()`（与 orchestrator 设备加载逻辑重复，全项目无引用）
- 修正 CLAUDE.md 设备仿真数据路径（`backend/app/hardware/` → `hardware_info/`）
- `ProviderConfig` / `LLMInfoResponse` 加 `protected_namespaces=()`，消除 Pydantic `model_name` 警告
- 新增版本管理细则（写进 CLAUDE.md，规范 MAJOR/MINOR/PATCH 的触发场景）

## [1.3.0] - 2026-08-16

### Added

- **用户认证（JWT）**：`security.py` 从空壳实装（PBKDF2 密码哈希 + PyJWT HS256 签发/验签）；新增 `POST /api/v1/auth/login`（账号密码换令牌，默认 7 天有效）+ `GET /api/v1/auth/me`；`AUTH_ENABLED=true` 后所有 `/api/v1/*` 端点强制登录（auth 路由单独挂载不受影响）
- **演示账号**：启动时自动创建 `admin` / `operator` / `reviewer` 三个角色账号（密码可经 `.env` 的 `AUTH_ADMIN_PASSWORD` 等配置，默认 `admin123` / `operator123` / `reviewer123`），users 表为空时幂等填充
- **RBAC 接入**：`require_role()` 依赖工厂；实验审核端点（approve/reject）仅限 `reviewer`/`admin` 角色；`permission.py` 角色扩展为 admin/operator/reviewer（保留 user/viewer 兼容）
- **审核人联动账号**：`GET /reviewers` 改为从 users 表查 `reviewer`/`admin` 角色账号（原为实验员表）
- **SSE 鉴权**：`GET /experiments/events` 单独挂载，支持 `?token=` query 参数鉴权（EventSource 无法带 header）
- **前端登录页**：`LoginPage.tsx`；`api.ts` 统一携带 `Authorization` header，401 自动清 token 并跳回登录页；顶部显示当前用户/角色 + 退出按钮；实验中心 SSE 自动带 token
- **认证测试**：`tests/test_auth.py` 7 个用例（登录成功/失败、伪造 token、角色越权 403、审核人列表、SSE 鉴权、/auth/me 软认证）

### Fixed

- **experiments 表缺列修复**：本地数据库 `experiments.reviewed_by_id` 列缺失导致启动时 Alembic 后 create_all 查询报错（`no such column`），已补列修复
- **前端冷启动不跳登录页**：`/auth/me` 改用软认证（`get_current_user_optional`），认证开启但未登录时返回 `auth_enabled=true` 而非 401，前端据此正确显示登录页
- **登录失败误触发全局过期**：`request()` 对 `/auth/*` 端点的 401 不再清 token / 派发 `auth:expired` 事件
- **审核人 ID 类型对齐**：`ReviewRequest.reviewer_id` 从 str 改为 int（与 users 表主键对齐，非数字 ID 由 Pydantic 直接 422，不再 500）
- **JWT 默认密钥加长**：`JWT_SECRET_KEY` 默认值从 23 字节加长到 48 字节，消除 PyJWT `InsecureKeyLengthWarning`

## [1.2.0] - 2026-08-15

### Added

- **实验审核**：实验跑完生成报告后进入「待审核」（不再直接「已完成」）；`POST /experiments/{id}/approve` + `/reject` 端点，通过→归档「已完成」、驳回→「已驳回」；记录审核人 ID/姓名/时间/意见（Alembic 005 迁移加 reviewed_by / reviewed_by_id / reviewed_at / review_comment 字段）
- **审核人选择**：新增 `GET /reviewers` 端点（当前返回实验员列表，将来账号管理完善后改查有审核权限的账号）；前端详情页「待审核」时显示审核人下拉（默认当前操作员，可选他人），替代原先写死「操作员本人」为审核人
- **待审核可查看报告**：报告文件在进入「待审核」时已生成，前端在「待审核」状态也显示「生成/下载报告」按钮，审核人可先看报告再决定通过/驳回

### Fixed

- 报告结论文本「实验已完成」改为「实验执行完成」，与「待审核」状态语义一致

## [1.1.0] - 2026-08-15

### Added

- **实验报告自动生成**：`report_generator.py` 生成 Word 报告（信息表/方案步骤/步骤执行/测量数据/审计记录/结论）+ Excel 数据表（多指标分 sheet）；实验完成时自动生成，文件存 `storage/reports/{id}/`；`GET /experiments/{id}/report` 端点 + `generate_experiment_report` Agent 工具（单轮完成）
- **追溯视图**：`GET /experiments/{id}` 返回 audits 时间线 + protocol 名称 + sample 信息；前端实验中心展示"执行记录"时间线
- **油化仿真设备**：设备从 `hardware_simulation_data.json` 加载（HTHP-01/02 失水仪、Rheo-01/02 六速流变仪、Thick-01/02 稠化仪），替换 5 台通用假设备；HTHP-01 漏失量 7 点插值 30 点
- **SSE 实验事件**：orchestrator 事件广播（experiment_status/step_status/measurement）+ `GET /experiments/events` SSE 端点；前端 EventSource 实时更新替换 3 秒轮询
- **实验员选择**：`GET /experimenters` 端点，前端一键开始弹操作员下拉 + 样品号输入

### Fixed

- **设备不复位**：MockDriver 加 `reset()`（指标回初始值/曲线索引清零），orchestrator start 时复位实验设备；修复第二次实验测量值直线问题
- **BUSY 状态**：设备状态四态透传（idle→online/busy/error/offline），硬件面板显示"忙碌"
- **send_command**：从 DriverRegistry 取设备下发指令，不再走写死列表（HTHP-01 不再 404）
- **created_at 类型**：Experiment.created_at String→DateTime（Alembic 004 batch 迁移）
- **超轮数不污染记忆**：达到最大工具调用轮数的系统提示不写入 Memory
- **设备三套账统一**：devices 表 seed（原 R-101/GC-2030 等 5 台旧设备）、DriverRegistry（6 台油化仿真设备）、hardware.py 兜底（原 rct-01 等又 5 台）三本账各记各的，导致「数据管理」和「硬件面板」显示不同设备；统一为 DriverRegistry 的 6 台油化仿真设备（SEED_DEVICES 对齐、hardware.py 删除 `_DEVICES` 兜底）
- **实验恢复**：orchestrator 加 `recover()`，main.py 启动时恢复重启前 status 为「执行中」的实验（重置卡住的 running 步骤 + 重启后台主循环），修复进程重启后实验卡死
- **send_command 进抽象接口**：`DeviceDriver` 基类补 `send_command` 抽象方法（原仅 MockDriver 有，换真实驱动会崩）
- **旧指标名修正**：query_hardware_history 参数描述从旧设备指标（温度/压力/液位）改为真实指标（温度/漏失量/转读数/稠化时间）
- **SSE 路由顺序**：`GET /experiments/events` 原注册在 `GET /experiments/{experiment_id}` 之后，被参数路由抢先匹配成「实验不存在: events」导致 SSE 404、前端实时更新失效；挪到参数路由之前
- **recover 只恢复「执行中」**：原 recover 查询含死状态「待执行」（代码里从无地方设置该状态），改为只恢复 running
- **设备数据加载容错**：`_register_devices` 加载仿真数据失败时记警告并注册 0 台，不再抛异常导致硬件端点 500
- **结果查询统一**：`query_experiment_result` 工具改走 `orchestrator.get_measurements()`，不再直查数据库表；`list_devices` 删除无用 refresh 参数

## [1.0.0] - 2026-08-14

### Added

- **实验域完整闭环（M1-M7）**：从"选方案 → 一键开始 → 设备逐步执行 → 实时数据 → 全程追溯"的自动化实验主线打通
- **M1 数据模型**：新增 6 张表（experimenters/protocols/protocol_steps/materials/experiment_steps/measurements），扩表 experiments(+operator_id/protocol_id/sample_code) 和 samples(+material_id)，含 Alembic 迁移 003
- **M3 设备驱动层**：`DeviceDriver` 抽象接口 + `MockDriver` 剧本引擎（受控升温/恒温/测量，含 HTHP 漏失量曲线）+ `DriverRegistry` 设备占用管理
- **M2 编排引擎**：`Orchestrator` 实验状态机（草稿→待执行→执行中→完成/异常/中止）+ 步骤展开 + 主循环 + 异常冻结/重试/跳步/中止
- **M5 交互层**：12 个实验域 REST 端点（方案库/实验 CRUD/进度/测量/看板）+ 5 个实验域 Agent 工具（list_protocols/create_experiment/start_experiment/query_progress/query_result）
- **M6 数据采集**：实验级 measurements 落库，measure 步骤按 complete_criteria 采 N 个数据点
- **M7 审计追溯**：`ExperimentAudit` 表 + 实验关键动作审计（create/status/step_succeed/step_fail）
- **前端「实验中心」Tab**：三视角（方案库 + 实验列表/看板 + 实验详情/数据），一键开始实验，3 秒轮询进度

### Changed

- 版本号跳跃至 1.0.0（演示版主链路闭环）
- 种子数据真实化：HTHP 高温高压失水仪实验方案（PROTO-001，3 步骤：升温→恒温→测量漏失量）

### 底层打通（系统性整合）

- **统一设备源**：三套独立设备体系（前端写死 / 后端 `_DEVICES` / DriverRegistry）合并为单一 DriverRegistry 源——6 台设备（HTHP-01 + 5 台通用）统一注册，硬件 API 从 DriverRegistry 读，前端 HardwarePanel 改为从后端 API 读取（替代写死的 seedDevices）
- **实验完成自动画图**：Orchestrator 在实验 completed 后自动调 plot_chart 生成漏失量曲线，结果摘要 + 图表 base64 存入 `experiments.result` 字段
- **数据丰富**：漏失量 7 个关键点线性插值成 30 点（平滑曲线），升温过程记录温度起止点
- **实验记录联动**：实验完成后结果可经 API 查询，前端实验中心展示曲线图 + 摘要

## [0.17.0] - 2026-08-13

### Added

- **Agent 工具调用迁移到原生 function calling**：模型直接输出结构化 `tool_calls`（参数由 API 协议保证合法），工具结果以 `role="tool"` 消息回传，模型自主决定继续调用/重试/给最终回答
- `ToolManager.list_tools_schema()`：把工具元数据转为 OpenAI tools 协议格式，统一规范化扁平参数为 JSON Schema
- `AgentManager.chat_with_tools()` / `chat_stream_with_tools()`：function calling 循环主链路，含 `max_iterations=8` 防死循环、工具往返不写 Memory、图片数据走 SSE chart 事件不进 LLM 上下文
- `ChatMessage` 增加 `tool_call_id` / `tool_calls` 字段；`LLMClient.chat()` 透传 `tools` 参数
- provider 消息序列化支持 `role="tool"` 消息和 assistant `tool_calls`；响应解析透传 `tool_calls`
- **系统顶层设计文档**（`docs/system_design.md`）：定义系统定位（实验管理系统与硬件设备之间的中间层）、演示版/生产版目标、M1-M7 模块划分（数据模型/编排引擎/设备驱动/系统对接/交互层/数据采集/审计追溯）及模块构建依赖顺序

### Fixed

- 工具 parameters 混合格式导致 function calling 400：14 个工具的扁平参数字典被规范化为标准 JSON Schema

### Changed

- 前端"思考过程"从"预先生成的计划清单"改为"实时工具调用流"（`ToolCallInfo.step_id` → `call_index`）
- 流式端点事件序列：移除 planning 事件，改为 thinking → tools → chunk → done
- 旧的 Planner(手写 JSON 计划) / Executor 链路保留但主调用方已切到 function calling

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
