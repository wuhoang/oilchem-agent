# OilChem Agent 项目全景报告

> 生成时间：2026-08-18
> 当前版本：v2.1.2，develop 分支
> 用途：与 GPT 讨论项目现状、架构设计、提示词策略的完整上下文

---

## 一、项目定位

OilChem Agent 是石油化工/化学实验室的 AI 助手，定位为「人-硬件-软件-网页」的中间层。核心价值是**全流程可追溯**：谁用了什么设备、消耗了什么样品、按什么方案执行、产出了什么数据。

- 技术栈：Python 3.12 + FastAPI + SQLAlchemy (aiosqlite) | React 18 + TypeScript + Vite + TailwindCSS
- 实际 LLM：DeepSeek API（`deepseek-chat`，OpenAI 兼容接口）
- 用户背景：油化领域出身，软件不太熟但对硬件接口更了解

---

## 二、系统架构

### 2.1 整体结构

```
前端 (React SPA, :5173)
  ├── NavRail (w-14, 5个图标导航)
  ├── 功能区 (实验中心/文件/硬件/数据/网页填表)
  └── ChatPanel (w-96, 常驻右侧, 可折叠)
        └── ChatWindow (SSE 流式消费)

后端 (FastAPI, :8000)
  ├── /api/v1/auth/* (登录/me, 单独挂载不走全量鉴权)
  ├── /api/v1/experiments/events (SSE, 单独挂载)
  ├── /api/v1/* (其余端点, AUTH_ENABLED=true 时全量鉴权)
  └── 内部管线:
        AgentManager ─ function calling ─▶ 25个工具 (按context路由)
                    ─▶ MemoryManager (滑动窗口20条)
                    ─▶ LLMClient (DeepSeek, 30s超时)
```

### 2.2 前端三栏布局（v2.0.0）

| 列 | 组件 | 宽度 | 内容 |
|---|---|---|---|
| 左 | NavRail | w-14 (56px) | 5 个图标按钮：实验/文件/硬件/数据/网页 |
| 中 | 动态面板 | flex-1 | 5 个 Tab 页面：ExperimentCenter / FileBrowser / HardwarePanel / DatabasePanel / WebFormPanel |
| 右 | ChatPanel | w-96 (384px) 或折叠 w-10 | 会话列表 + ChatWindow + 折叠按钮 |

聊天不再是 Tab——用户在任何功能页面都能直接对话，当前页面作为 context 传给后端做工具路由。

### 2.3 请求流转（以 SSE 流式对话为例）

```
前端 ChatWindow.sendChatMessageStream()
  → POST /api/v1/chat/stream
    → InputGuardrail.check()          // Prompt 注入检测 + 敏感信息脱敏
    → AgentManager.chat_stream_with_tools()
      → MemoryManager.add_message()   // 存储用户消息
      → yield "thinking" 事件         // 进度反馈
      → ToolManager.list_tools_schema(categories)  // 按context过滤工具
      → for iteration in range(8):    // 工具循环
            → LLMClient.chat()        // 非流式，模型决定调工具还是回答
            → if tool_calls:
                → yield "tools/start"
                → ToolManager.execute()
                → yield "tools/complete"
                → if image_base64: yield "chart"
            → else: break
      → LLMClient.stream_chat()       // 流式最终回复（打字机效果）
      → yield "chunk" × N
      → yield "done"
    → OutputGuardrail.check()         // 审计日志
```

### 2.4 工具路由（按页面上下文）

| 前端页面 | 加载的工具类别 | 工具数量 |
|---|---|---|
| experiments | experiment + chart + file | 12 |
| hardware | hardware + chart | 4 |
| files | file + office | 12 |
| database | file | 5 |
| webform | web | 4 |
| 无/聊天 | 全部 | 25 |

---

## 三、核心模块

### 3.1 Agent 对话循环（manager.py）

两个入口方法，功能等价，区别在最终回复阶段：
- `chat_with_tools()`：同步，返回完整响应（REST 端点用）
- `chat_stream_with_tools()`：异步生成器，逐块推送 SSE 事件（流式端点用）

**四道安全保障：**

| 防线 | 机制 | 解决什么 |
|---|---|---|
| 重复调用检测 | `call_history` 记录 (tool_name, args_hash)，重复出现强制退出 | 「反复调同一个东西」 |
| 墙钟超时 120s | `time.monotonic()` 每轮检查 | 「无限等待」 |
| 最大迭代 8 轮 | `for _ in range(8)` + `else` 分支 | 「工具循环停不下来」 |
| SSE 进度事件 | 每轮发 `thinking` 事件 | 「卡住无反馈」 |

**Memory 管理：** 滑动窗口 20 条消息，超出自动压缩（保留最近 10 条 + 摘要）。工具往返不写 Memory，只存最终回复。

### 3.2 编排引擎（orchestrator.py）

状态机：

```
草稿 → 执行中 → 待审核 → 已完成（审核通过）
                    ↓
                  已驳回（审核驳回）
执行中 → 异常（步骤失败）
执行中 → 中止（手动中止）
```

**核心流程：**
1. `start()` → 展开步骤 → 复位设备 → 后台 `_run_loop()`
2. `_run_loop()` → 逐步执行 → 设备占用/释放 → 测量数据落库 → SSE 事件广播
3. 全部步骤完成 → 生成结果图表 + Word/Excel 报告 → 进入「待审核」
4. `approve()` / `reject()` → 最终归档

**异常处理：** 步骤失败冻结在「异常」→ 用户可 `retry_step()` / `skip_step()` / `abort()`。进程重启后 `recover()` 自动恢复卡在「执行中」的实验。

### 3.3 设备驱动层

```
DeviceDriver (ABC)
  └── MockDriver (剧本化模拟器)
        └── 从 hardware_simulation_data.json 加载曲线数据

DriverRegistry (设备注册表)
  └── 6 台油化仿真设备：HTHP-01/02, Rheo-01/02, Thick-01/02
```

`DeviceDriver` 接口：connect / disconnect / execute_step / read_telemetry / get_status / cancel / send_command / reset。

**当前全是 Mock**——没有真实 RS232/USB/GPIB 通信代码。接真实设备需要新建驱动类（~500-1000 行/设备类型）+ 传输抽象层。

### 3.4 数据库（16 张 ORM 表）

| 分类 | 表 |
|---|---|
| 用户/会话 | users, sessions, messages |
| 审计/知识 | tool_audits, knowledge |
| 实验域 | experiments, experiment_steps, measurements, experiment_audits |
| 方案域 | protocols, protocol_steps |
| 设备域 | devices, device_telemetry_history |
| 样品/材料 | samples, materials, experimenters |

`init_db()` 三阶段：Alembic 迁移 → create_all（幂等补建）→ 种子数据（幂等填充）。

### 3.5 认证与权限

- JWT 登录（PBKDF2 密码哈希 + PyJWT HS256）
- `AUTH_ENABLED` 开关：false 时全部放行，true 时全量鉴权
- 三个角色：admin（全权限）/ operator（跑实验，不能审核）/ reviewer（审核实验）
- 登录限流：5 次/5 分钟/IP
- SSE 走 `?token=` query 参数（EventSource 无法带 header）

### 3.6 25 个工具

| 类别 | 工具 | 数量 |
|---|---|---|
| experiment | list_protocols, create_experiment, start_experiment, query_experiment_progress, query_experiment_result, generate_experiment_report | 6 |
| hardware | read_hardware, send_hardware_command, query_hardware_history | 3 |
| file | read_file, write_file, append_file, list_files, delete_file | 5 |
| office | read_excel, write_excel, read_word, write_word, read_ppt, write_ppt | 6 |
| web | browse_webpage, smart_fill_form, fill_webform, extract_webpage_text | 4 |
| chart | plot_chart | 1 |

---

## 四、提示词设计策略

### 4.1 整体结构（7 个段落）

1. **角色身份**：实验助手 / 设备网关 / 数据管家 / 网页操作员
2. **核心能力**：6 个能力域（文件/分析/报告/网页/设备/数据库）
3. **网页工具指南**：smart_fill_form 优先，含 JSON 示例
4. **硬件设备指南**：动态设备表（从 DriverRegistry 实时生成）+ 3 条工具选择规则
5. **工具使用原则**（v2.1.0 重写）：效率优先的 4 条规则
6. **回答风格**：先给结论、附单位判断、工具结果直接整合
7. **严格禁止**：6 条硬性禁令

### 4.2 工具使用原则（核心改动）

从「鼓励探索」改为「鼓励效率」：

| 原则 | 说明 | 示例 |
|---|---|---|
| 能不用就不用 | 常识问题直接回答 | 「HTHP 漏失量正常范围」→ 直接答（领域知识） |
| 能一步就不分步 | 最少工具调用 | 「生成报告」→ 只调 generate_experiment_report |
| 失败就停 | 不自动重试 | 设备不存在 → 直接告知，不换参数重试 |
| 有答案就收手 | 拿到数据就回答 | 读到 Excel → 直接分析，不再读更多 sheet |

### 4.3 三层反循环保护

| 层 | 位置 | 机制 |
|---|---|---|
| 提示词层 | 系统提示词 | 禁止重复调用、连续 2 次无新信息强制停止 |
| 代码层 | manager.py | `call_history` 检测相同 (name, args)，重复则 break |
| 硬限制 | manager.py | 最大 8 轮迭代 + 120 秒墙钟超时 |

### 4.4 按上下文裁剪提示词

- experiments / hardware：包含领域知识（钻井液测试标准、安全操作）
- files / database / webform：省略领域知识（省 ~700 token）
- 无 context / chat：全部包含

### 4.5 提示词已知缺口

1. 缺少多工具链的 few-shot 示例（单工具有示例，多步没有）
2. database 上下文只加载 file 工具（没有数据库查询工具）
3. 「2 次失败停止」只靠 LLM 自律，代码层未强制
4. 领域知识裁剪太粗（分析钻井液 Excel 时也丢失了领域上下文）
5. 缺少「工具不可用时怎么告知用户」的指令

---

## 五、测试覆盖

### 5.1 现有测试（23 个）

| 文件 | 数量 | 覆盖范围 |
|---|---|---|
| test_bootstrap.py | 2 | 启动冒烟：根路由、健康检查 |
| test_auth.py | 7 | 登录成功/失败、伪造 token、RBAC 403、审核人列表、SSE 鉴权、/me 软认证 |
| test_guardrails.py | 6 | 正常通过、空输入、注入检测、jailbreak、脱敏、超长输入 |
| test_orchestrator.py | 8 | 创建实验+详情、启动404、审核400、中止400、重试404、跳过404、审核人列表、看板 |

### 5.2 未覆盖的关键路径

- Agent 聊天循环（chat_with_tools / chat_stream_with_tools）—— 零测试
- 工具执行层（25 个工具各自的行为）—— 零测试
- 编排器主循环（_run_loop、步骤执行、测量记录）—— 只有 API 级测试，无单元测试
- MemoryManager（压缩、上下文生成）—— 零测试
- LLM 客户端（重试逻辑、provider 切换）—— 零测试
- 报告生成器 —— 零测试

---

## 六、已知问题与技术债

### 6.1 架构级

| 问题 | 严重度 | 说明 |
|---|---|---|
| 全局单例无 DI | 中 | get_agent() / get_orchestrator() / settings 模块级单例 |
| Memory 纯内存 | 中 | 进程重启丢失所有会话 |
| 实验域无外键约束 | 高 | 10+ FK 列是纯 String，无 ForeignKey() 声明，无参照完整性 |
| 编排器直接访问 DB | 中 | 设计文档要求注入 Repository，实际直接用 get_session_factory() |

### 6.2 安全级

| 问题 | 严重度 | 说明 |
|---|---|---|
| CORS 全开 | 中 | allow_origins=["*"] |
| 聊天无限流 | 中 | 登录有 5 次/5 分钟限流，聊天没有 |
| JWT 默认密钥 | 低 | 开发默认值，无启动检查 |
| DB 端点任意列覆盖 | 中 | insert/update 接受任意 dict，可改 experiments.status 绕过审核 |

### 6.3 功能级

| 问题 | 说明 |
|---|---|
| 硬件全 Mock | 无真实 RS232/USB/GPIB 通信 |
| MCP 写了没接 | mcp/client.py 完整但从未被引用 |
| 旧设计文档过时 | system_design.md / detailed_design.md 未反映 v1.2.0 后的变更（审核、认证、报告） |
| database 上下文缺工具 | CONTEXT_TOOL_MAP 里 database 只映射 file，没有 DB 查询工具 |
| Playwright 限制 | 无反反爬虫、无 iframe、无持久化状态 |

### 6.4 时间线债务

`datetime.utcnow()` 已全部替换（26 处 → `datetime.now(datetime.UTC).replace(tzinfo=None)`），弃用警告归零。但 SQLite 存储的是 naive datetime，将来换 PostgreSQL 需要重新处理时区。

---

## 七、版本演进

| 版本 | 日期 | 核心变更 |
|---|---|---|
| 0.15.0 | 08-10 | Guardrails 接入 + DB 端点转 ORM |
| 0.16.x | 08-10~13 | 硬件遥测采集、DeepSeek 默认、路径清理 |
| 0.17.0 | 08-13 | 迁移到原生 function calling |
| 1.0.0 | 08-14 | 实验域 M1-M7 端到端闭环 |
| 1.1.0 | 08-15 | 报告自动生成 + 油化仿真设备 |
| 1.2.0 | 08-15 | 实验审核（待审核/通过/驳回） |
| 1.3.0 | 08-16 | 用户认证（JWT + RBAC） |
| 1.3.1~1.3.3 | 08-16 | 清理、bug 修复、P0 聊天崩溃修复 |
| 2.0.0 | 08-16 | 三栏布局 + 工具路由 |
| 2.0.1 | 08-16 | SSE 订阅修复 |
| 2.1.0 | 08-17 | 对话提示词重构（效率优先）+ 反循环检测 |
| 2.1.1 | 08-17 | 重复调用检测 bug 修复 |
| 2.1.2 | 08-18 | 删除死代码 ~500 行 + utcnow 修复 + 测试 9→23 |

---

## 八、与 GPT 讨论的建议话题

1. **提示词优化**：当前的「效率优先」策略是否合理？对于 DeepSeek 模型，有没有更好的工具调用指导方式？多工具链的 few-shot 示例该怎么写？

2. **工具路由**：按页面上下文过滤工具子集的做法是否最优？有没有更智能的路由方式（比如意图分类）？

3. **测试策略**：23 个测试远远不够。应该优先补哪些测试？Agent 聊天循环怎么 mock LLM 来测？编排器状态机怎么测？

4. **架构演进**：全局单例和无 DI 的问题怎么逐步解决？Memory 持久化用什么方案？实验域外键约束怎么加（Alembic 迁移策略）？

5. **真实硬件通信**：DeviceDriver 接口设计是否足够抽象？接真实 RS232 设备需要补什么？传输层怎么设计？

6. **多 Agent 可行性**：当前 25 工具一个 Agent 处理，未来是否有拆分的必要？什么时候该引入多 Agent？

7. **安全加固**：CORS、限流、DB 端点任意覆盖——按什么优先级修？JWT 配置怎么做到生产级？

8. **设计文档更新**：system_design.md 和 detailed_design.md 已严重过时，是重新写还是增量更新？
