# OilChem Agent — 开发日志

> 本文档按版本逆序记录每一次功能迭代、缺陷修复和架构变更。
> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
> 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [2.1.2] — 2026-08-18

### Changed

- **删除旧 Planner→Executor 死代码**
  - 删除 `agent/planner/` 目录（planner.py 329 行 + __init__.py）
  - 删除 `agent/executor.py`（319 行）
  - 删除 `manager.py` 中 5 个死方法：`chat()`（旧 Planner 入口）、`plan()`、`execute_plan()`、`execute_step()`、`chat_stream()`（旧流式入口）
  - 删除 `manager.py` 中 2 个死辅助函数：`_build_thinking_content()`、`_build_tool_summary()`
  - 删除 `prompts.py` 中死函数 `get_planning_prompt_template()` 和未使用的 `LAB_AUTOMATION_PROMPT`
  - 清理 `agent/__init__.py` 和 `agent/prompts/__init__.py` 的死重导出
  - 清理 `manager.py` 的死导入（Planner/Executor/Plan/PlanStep/ExecutionResult/StepResult）
  - 更新 `manager.py` 模块文档字符串（移除 Planner/Executor 引用）
- **修复 `datetime.utcnow()` 弃用（26 处）**
  - `tables.py`：添加 `_utcnow()` 辅助函数（`datetime.now(datetime.UTC).replace(tzinfo=None)`），替换 17 处 ORM 默认值
  - `orchestrator.py`：替换 5 处运行时调用
  - `mock.py`/`base.py`/`hardware_tools.py`/`hardware_collector.py`：替换 4 处
  - 保持 naive UTC 格式兼容 SQLite 存储
- **清理未使用导入和过时引用**
  - `tables.py`：移除 `Column`、`UniqueConstraint`（从未使用）
  - `registry.py`：文档示例从 `rct-01` 改为 `HTHP-01`
- **新增测试 14 个**
  - `test_orchestrator.py`（8 个）：编排器集成测试——创建实验+查详情、启动不存在实验404、审核非待审核实验400、中止非执行中实验400、重试/跳过不存在实验404、实验员审核人列表、看板统计
  - `test_guardrails.py`（6 个）：输入护栏单元测试——正常通过、空输入拒绝、Prompt 注入检测、jailbreak 检测、敏感信息脱敏、超长输入拒绝
  - 总测试从 9 个增至 23 个
- 版本号 2.1.1 → 2.1.2

---

## [2.1.1] — 2026-08-17

### Fixed

- **反循环检测未真正停止主循环**
  - 现象：2.1.0 的 duplicate 检测 `break` 位于内层 `for tc in msg.tool_calls` 中，只跳出内层循环；主循环继续后把带悬空 tool_calls（缺少 role=tool 响应）的 messages 发给 LLM，API 必返 400
  - 后果：多一轮注定失败的请求；非流式路径触发 `except` 降级为 `_direct_chat` 无工具对话，丢失工具上下文与「已获取足够信息」文案；流式路径靠 final_response 兜底但日志出现 tools 请求失败 warning
  - 修复：两条路径均引入 `duplicate_stop` flag——duplicate 时置 True，`for tc` 结束后 `if duplicate_stop: break` 跳出主循环，立即返回「已获取足够信息，正在整理回答...」，不再发多余的 LLM 请求

### Changed

- 版本号 2.1.0 → 2.1.1

## [2.1.0] — 2026-08-17

### Changed

- **对话提示词重构（迭代 1）**
  - 删除 `prompts.py` 中「思考方式」段落（拆 3-5 步 + 必须多步 + 提出替代方案），替换为「工具使用原则」（能不用就不用 + 能一步就不分步 + 失败就停 + 有答案就收手）
  - 新增「回答风格」（先给结论再给细节、工具结果直接整合进回答）
  - 强化「严格禁止」（禁止重复调用、禁止暴露工具计划、禁止为完整性调用未要求的工具、连续 2 次无新信息强制停止）
  - 参考了 Claude Code、LangChain ReAct、OpenHands CodeAct 等成熟 Agent 的提示词设计
- **工具循环反循环检测（代码层）**
  - `manager.py` 两个路径（stream / non-stream）均加 `call_history: list[tuple[str, str]]`，记录 `(tool_name, json.dumps(args, sort_keys=True))`
  - 相同 key 重复出现时 `break` 退出循环 + 记 warning 日志
- **墙钟超时 120 秒**
  - `time.monotonic()` 记录循环开始时间，每轮检查是否超 120 秒
  - 超时后设 `final_response` + `skip_memory = True`，跳出循环
- **SSE 进度事件**
  - 流式路径每轮迭代开始时 `yield AgentStreamEvent(type="thinking", content="正在处理第 N 步...")`
  - 保持 SSE 连接活跃，前端不再「卡住无反馈」
- **Memory 滑动窗口**
  - `memory.py` 的 `ConversationMemory.max_messages` 从 50 降至 20
  - 超出时自动压缩（保留最近 10 条 + 摘要）

> 注：这是一次对话体验的迭代尝试，还会继续调整优化。下一步计划：工具描述加「何时不该用」说明、SSE keepalive 注释行、流式路径 LLM 失败降级。

### Changed

- 版本号 2.0.1 → 2.1.0

---

## [2.0.1] — 2026-08-16

### Fixed

- **聊天发起的实验不实时出现在实验中心**
  - 现象：在常驻聊天面板让 Agent 开始高温高压失水实验，工具调用成功（日志/DB 确认实验真实创建并跑完），但实验中心列表看不到，需手动刷新或切换 Tab 重新挂载
  - 根因：`ExperimentCenter.tsx` 的 SSE 订阅嵌套在 `if (selectedExperiment)` 内，未选中实验时无订阅；列表与统计只在挂载时拉取一次
  - 修复：SSE 改为挂载即订阅（新增 `selectedExperimentRef` 供回调读最新选中值，避免切换选中时重连事件流）；`experiment_status` 事件触发 `loadAll()` 刷新列表与看板，事件属于选中实验时 `refreshDetail()`；选中实验变化单独一个 effect 拉详情

### Changed

- 版本号 2.0.0 → 2.0.1

## [2.0.0] — 2026-08-16

### Added

- **常驻聊天面板 + 三栏布局**
  - 新建 `NavRail.tsx`：w-14 窄图标导航（实验/文件/硬件/数据/网页 5 个入口），取代原 Sidebar 导航与 header Tab 栏
  - 新建 `ChatPanel.tsx`：w-96 常驻右侧面板 = 顶栏（折叠/新建）+ 会话列表（原 Sidebar.tsx 逻辑整体移入，max-h-44 摘要区）+ ChatWindow；折叠态退化为 w-10 窄条（单个展开按钮）
  - `App.tsx` 重构为三栏：NavRail + 功能区 + ChatPanel；activeTab 从 6 个（含 chat）缩减为 5 个功能 Tab，默认 experiments；聊天不再受 Tab 切换影响
  - `ChatWindow.tsx` 嵌入式改造：去独立 header 会话标题（上移 ChatPanel 顶部），保留消息数/正在思考/停止生成；新增 context prop
  - `Sidebar.tsx` 删除（被 NavRail + ChatPanel 取代）
- **工具路由（按页面上下文）**
  - `tools/base.py`：ToolMetadata 新增 `category: str = "general"`；6 个工具文件 25 个工具全部打标：file×5 / office×6 / web×4 / chart×1 / hardware×3 / experiment×6
  - `tools/manager.py`：`list_available_tools()` / `list_tools_schema()` 新增 `categories: list[str] | None` 过滤参数
  - `agent/manager.py`：`AgentChatRequest` 新增 `context` 字段；`CONTEXT_TOOL_MAP`（experiments→experiment/chart/file，hardware→hardware/chart，files→file/office，database→file，webform→web；未列出→全部）；`chat_with_tools` / `chat_stream_with_tools` 按 context 加载工具子集
  - `chat.py`：`ChatRequest` 新增 `context`，两个端点透传
  - `prompts.py`：`get_system_prompt(context=...)` 按上下文裁剪领域提示词（files/database/webform 省约 700 字符）；保持 replace() 填充设备表方案不变
- **前端类型**：`types/index.ts` ChatRequest 新增 `context?: string | null`

### Changed

- 版本号 1.3.3 → 2.0.0（MAJOR：UI 架构变更——三栏布局 + 常驻聊天面板）

## [1.3.3] — 2026-08-16

### Fixed

- **聊天主链路崩溃（P0）**
  - prompts.py 动态设备表用 DEFAULT_SYSTEM_PROMPT.format(device_table=...) 填充，但提示词正文「网页工具使用指南」里有 JSON 示例大括号（{"字段名": "值"}、field_mapping={...}），str.format() 把它们误当占位符解析，get_system_prompt() 必抛 KeyError: '"字段名"'
  - 影响面：前端聊天不传自定义 system_prompt，后端 chat.py / manager.py 共 4 处走 get_system_prompt()，每次聊天必失败（现有 9 个测试不覆盖聊天路径，未拦住）
  - 修复：改用 DEFAULT_SYSTEM_PROMPT.replace("{device_table}", _build_device_table())，只替换单一占位符
- **审核人默认值混用（A1）**
  - 前端 reviewerId = selectedReviewer || selectedOperator 在未选审核人时把实验员 ID（OP-001 字符串）传给后端 ReviewRequest.reviewer_id（int）→ Pydantic 422
  - 修复：api.ts 新增 Reviewer 接口（id: number）与 Experimenter（id: string）区分；ExperimentCenter.tsx 加载时默认选中第一个审核账号；下拉显示值与 option value 字符串化
- **中止按钮无状态限制（A2）**
  - 前端「中止实验」按钮无条件渲染；后端 abort() 无状态校验，「已完成」实验可被改成「中止」
  - 修复：前端仅 status === "执行中" 显示按钮；后端 abort() 校验状态非执行中抛 ValueError；abort 端点补 ValueError→400 / KeyError→404
- **start 可重复展开步骤（A3）**
  - start() 只查运行时任务表，对已完成实验再调 start 会重复 _expand_steps 插入步骤并重跑，测量数据翻倍
  - 修复：start() 校验实验状态仅「草稿」/「待执行」可启动，否则 ValueError；start 端点补 KeyError→404
- **retry/skip 端点缺异常处理（A4）**
  - retry_step / skip_step 端点不捕获 orchestrator 的 ValueError，重复操作返回 500 而非 400；补 try/except 映射 400

### Changed

- 版本号 1.3.2 → 1.3.3

## [1.3.2] — 2026-08-16

### Fixed

- **系统提示词设备表过时**：prompts.py 中的设备表（rct-01/gc-01 等 5 台幻影设备）替换为实际 6 台设备（HTHP-01/02、Rheo-01/02、Thick-01/02），含 GGS42-2A/ZNN-D6/OWC-2000D 型号和真实指标名；`OILCHEM_DOMAIN_PROMPT` 从石油炼制工艺改为钻井液测试（HTHP 失水量/流变参数/稠化时间/相关标准 API RP 13B-1 等）
- **orchestrator `_release_devices` 释放全部设备**：改为查询 `ExperimentStep` 只释放当前实验的设备
- **orchestrator `retry_step`/`skip_step` 缺防重入**：加 `if experiment_id in self._tasks: raise ValueError` 保护
- **步骤超时不执行**：`_run_loop` 中用 `asyncio.wait_for(self._execute_step(...), timeout=step.timeout_s)` 包裹，超时返回 `StepResult(success=False, status_code="timeout")`
- **`CancelledError` 处理器不设状态**：`_run_loop` 的 `except asyncio.CancelledError` 现在调用 `self._set_status(experiment_id, self.STATUS_ABORTED)`

### Added

- **登录限流**：`auth.py` 加内存级 IP 限流（`_LOGIN_MAX_ATTEMPTS=5`，`_LOGIN_WINDOW_S=300`），失败记 5 次后 5 分钟内返回 429；登录成功清除计数；无需新依赖

### Changed

- 版本号 1.3.1 → 1.3.2

---

## [1.3.1] — 2026-08-16

### Changed

- 删除 `mock.py` 死代码 `load_hthp_behavior()`（与 orchestrator 设备加载重复）
- 修正 CLAUDE.md 设备仿真数据路径（`backend/app/hardware/` → `hardware_info/`）
- `ProviderConfig`/`LLMInfoResponse` 加 `protected_namespaces=()` 消除 Pydantic 警告
- 新增版本管理细则（写进 CLAUDE.md，规范 MAJOR/MINOR/PATCH 触发场景）
- 版本号 1.3.0 → 1.3.1

## [1.3.0] — 2026-08-16

### Added

- **用户认证（JWT）**
  - `core/security.py` 从空壳实装：PBKDF2-HMAC-SHA256 密码哈希（标准库，零依赖，格式 `pbkdf2$sha256$iterations$salt$hash`）+ PyJWT HS256 签发/验签（`create_access_token` / `decode_access_token`），密钥与过期时间读自 Settings（默认 7 天）
  - 新增 `api/v1/endpoints/auth.py`：`POST /auth/login`（账号密码换令牌，失败 401 不泄露原因）+ `GET /auth/me`（返回当前用户与 `auth_enabled` 状态，供前端启动探测）
  - `AUTH_ENABLED=true` 时全量鉴权：`api/v1/router.py` 的聚合 router 挂 `Depends(get_current_user)`；auth 路由与 SSE 路由单独在 `main.py` 挂载，避免被父级依赖拦截（登录端点自身不能要 token；EventSource 无法带 header）
  - 新依赖 `pyjwt`（已加入 pyproject.toml 并安装）
- **演示账号（种子）**
  - `database/session.py` 新增 `_seed_users()`：users 表为空时创建 `admin` / `operator` / `reviewer` 三个角色账号，密码取自 `.env`（`AUTH_ADMIN_PASSWORD` 等），未配置用默认值 `admin123` / `operator123` / `reviewer123`；幂等
- **RBAC 接入**
  - `api/deps.py` 新增 `get_current_user`（Header Bearer 解析 + 查库校验）、`get_current_user_query`（SSE/WS 用 query token）、`require_role(*roles)` 依赖工厂（403 拒绝）
  - 实验审核端点 `approve` / `reject` 挂 `require_role("reviewer", "admin")`；操作员调用返回 403
  - `guardrails/permission.py` 角色扩展：`Role` 增加 `OPERATOR` / `REVIEWER`，权限映射对齐实验流程（操作员可管理实验、审核人可审核），保留 user/viewer 兼容旧数据
- **审核人联动账号**
  - `GET /reviewers` 改为从 users 表查 `reviewer`/`admin` 角色账号（返回 `{id, name, role}`），不再查实验员表；approve/reject 同步改查 users 表并写入 `reviewed_by_id`（账号 ID）
- **SSE 鉴权**
  - `GET /experiments/events` 迁移到独立 `events_router`（experiments.py 内），在 `main.py` 单独挂载，端点内挂 `get_current_user_query`：AUTH 开启时 `?token=` 校验，无 token 401
- **前端登录**
  - 新增 `components/LoginPage.tsx`（账号密码表单，错误提示，演示账号说明）
  - `services/api.ts`：token 存 localStorage（`oilchem_token`），`request()` 统一携带 `Authorization` header，401 触发 `auth:expired` 全局事件并清 token；新增 `login()` / `fetchMe()` / `getToken()` / `setToken()`；`sendChatMessageStream` 同步加 header
  - `App.tsx`：启动时 `fetchMe()` 探测（后端不可达不拦截）；`authEnabled && !user` 时渲染登录页；顶部显示当前用户/角色 + 退出按钮；监听 `auth:expired` 回登录态；版本号 v1.3.0
  - `ExperimentCenter.tsx`：EventSource URL 自动携带 `?token=`
- **认证测试**：新增 `tests/test_auth.py`（AUTH_ENABLED=true 场景，7 用例）：未登录 401、登录成功 + 带 token 访问 200、错误密码 401、伪造 token 401、操作员调审核 403、reviewers 列表只含 reviewer/admin、SSE 无 token 401、/auth/me 软认证返回 auth_enabled

### Fixed

- **本地库缺列修复**：`experiments` 表缺 `reviewed_by_id` 列（Alembic 版本号已是 005 但列不在），导致启动时 create_all 后种子查询报 `no such column` 错误、数据库初始化失败；直接 ALTER TABLE 补列修复
- **前端冷启动不跳登录页**：`/auth/me` 改用软认证（`get_current_user_optional`），认证开启但未登录时返回 `auth_enabled=true` 而非 401；`request()` 对 `/auth/*` 端点的 401 不再清 token/派发过期事件；`ReviewRequest.reviewer_id` 改为 int 对齐 users 表主键

### Changed

- `JWT_EXPIRE_MINUTES` 默认 60 → 10080（7 天）
- `config.py` 新增 `AUTH_ADMIN_PASSWORD` / `AUTH_OPERATOR_PASSWORD` / `AUTH_REVIEWER_PASSWORD`
- 版本号 1.2.0 → 1.3.0

## [1.2.0] — 2026-08-15

### Added

- **实验审核（LIMS 方向预埋）**
  - 状态机新增「待审核」「已驳回」两个状态；实验跑完生成报告后进入「待审核」，不再直接「已完成」
  - `POST /experiments/{id}/approve` + `/reject` 端点：通过→「已完成」归档、驳回→「已驳回」；均校验当前状态必须为「待审核」
  - `Experiment` 加 4 个审核字段：`reviewed_by`（姓名）/ `reviewed_by_id`（ID，将来关联账号）/ `reviewed_at` / `review_comment`；Alembic 005 迁移
  - **审核人选择**：新增 `GET /reviewers` 端点（当前返回实验员列表，将来账号管理完善后改查有审核权限的账号）；前端「待审核」状态显示审核人下拉（默认当前操作员 = 可自审，可选他人），替代原先写死「操作员本人」为审核人
- **待审核可查看报告**：报告在进入「待审核」时已生成，前端在「待审核」状态也显示「生成/下载报告」按钮，审核人可先看报告再决定

### Fixed

- 报告结论文本「实验已完成」→「实验执行完成」，与「待审核」状态语义一致

### Changed

- 版本号 1.1.0 → 1.2.0

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
- **设备三套账统一（DSH 审计断点 1）**：
  - 问题：`devices` 表 seed（R-101/GC-2030/XS205/FE28/RP-100）、DriverRegistry（HTHP/Rheo/Thick 6 台）、`hardware.py` 兜底 `_DEVICES`（rct-01/gc-01 等）三本账各记各的，导致「数据管理」面板和「硬件面板」显示不同设备、实验方案引用的设备在台账查不到
  - 修复：`SEED_DEVICES` 改为 6 台油化仿真设备（与 DriverRegistry 对齐）；`hardware.py` 删除 `_DEVICES` 兜底和 `_refresh_metrics`，端点只读 DriverRegistry；`DeviceDriver` 基类补 `send_command` 抽象方法；query_hardware_history 参数描述改为真实指标
- **实验恢复（recover）**：orchestrator 加 `recover()`，启动时扫描 status=「执行中」的实验，把卡在 running 的步骤重置为 pending 并重启后台主循环；main.py lifespan 调用——修复进程重启后实验卡死在「执行中」

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
