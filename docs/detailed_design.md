# OilChem Agent 详细设计

> 文档定位：详细设计（Detailed Design）。
> 描述各模块内部的**表结构、类/接口签名、状态机、API 端点、事件规范**，作为实现的直接依据。
> 与 `docs/system_design.md`（顶层设计）的关系：本文是它的展开，模块划分 M1-M7 与构建顺序 M1→M3→M2→M6→M5→M7→M4 严格对齐。
> 与现有代码的关系：遵循"扩表不推翻"——已存在的表（experiments/samples/devices/telemetry）标注「扩」，新增表标注「新增」。

---

## 约定

- 主键：主数据/业务对象用**字符串业务编码**（如 `EXP-001`、`PROTO-001`），大量流水/明细数据用**自增整数**（如 measurements、experiment_steps）。
- 时间字段统一 `DateTime`（UTC），不再使用字符串存时间（现有 `experiments.created_at` 为字符串，需修正）。
- 关联字段命名：`xxx_id` 表示外键；可选外键标注「可空」。
- 参数/判据等结构化字段用 `Text` 存 JSON 字符串，序列化由业务层负责。

---

## 1. M1 数据模型详细设计

### 1.1 ER 关系总览

```
experimenters ──┐
                │ operator_id
                ▼
protocols ──protocol_id──▶ experiments ──sample_code──▶ samples ──material_id──▶ materials
    │                          │
    │ protocol_id              │ experiment_id
    ▼                          ▼
protocol_steps          experiment_steps（运行时步骤实例）
    │ device_id                │ experiment_step_id
    ▼                          ▼
devices ◀────────────▶ measurements（测量数据点）
```

### 1.2 各表字段定义

#### experimenters（实验员）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(32) | PK | 如 `OP-001` |
| name | String(64) | 非空 | 姓名 |
| role | String(32) | 非空 | 研究员/工程师/技术员 |
| department | String(64) | 可空 | 部门/课题组 |
| created_at | DateTime | 非空 | 创建时间 |

#### protocols（实验设计/方案）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(32) | PK | 如 `PROTO-001` |
| name | String(255) | 非空 | 方案名称 |
| description | Text | 可空 | 方案说明 |
| version | String(16) | 非空，默认 v1 | 方案版本（M7 追溯用） |
| status | String(32) | 非空 | 草稿/已发布/已归档 |
| created_at / updated_at | DateTime | 非空 | — |

#### protocol_steps（步骤模板）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK 自增 | — |
| protocol_id | String(32) | FK→protocols.id | 所属方案 |
| step_order | Integer | 非空 | 步骤序号（从 1） |
| device_id | String(32) | FK→devices.id | 目标设备 |
| action | String(64) | 非空 | 动作名（见 §3.4 动作表） |
| params | Text | 非空，JSON | 动作参数，如 `{"temperature": 180}` |
| timeout_s | Integer | 非空，默认 60 | 本步超时（秒） |
| complete_criteria | Text | 非空，JSON | 完成判据（见 §3.4） |
| description | String(255) | 可空 | 步骤说明 |

#### experiments（实验运行）— 扩现有表

现有字段保留：`id` / `name` / `status` / `updated_at`。
修正与新增字段：

| 字段 | 类型 | 变更 | 说明 |
|------|------|------|------|
| created_at | DateTime | **修正** | 原为 String(32)，改为 DateTime |
| operator | String(64) | **废弃** | 迁移为 operator_id，过渡期保留 |
| operator_id | String(32) | 新增，FK→experimenters.id | 操作实验员 |
| protocol_id | String(32) | 新增，FK→protocols.id | 采用的方案 |
| sample_code | String(32) | 新增，FK→samples.code | 使用的样品 |

> 说明：顶层设计提到的 `device_id` 不落在 experiments 上——一条实验可能涉及多台设备，设备归属在**步骤**（protocol_steps / experiment_steps）上表达。

#### experiment_steps（步骤执行实例）— 新增（M2 运行时落库）

这是方案步骤「实例化」后的运行记录，M7 追溯的核心载体。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK 自增 | — |
| experiment_id | String(32) | FK→experiments.id | 所属实验 |
| protocol_step_id | Integer | 可空，FK→protocol_steps.id | 模板来源 |
| step_order | Integer | 非空 | 执行序号 |
| device_id | String(32) | FK→devices.id | 目标设备 |
| action | String(64) | 非空 | 动作名 |
| params | Text | JSON | 实例化后的参数 |
| timeout_s | Integer | 非空 | 超时 |
| complete_criteria | Text | JSON | 完成判据 |
| status | String(32) | 非空 | pending/running/succeeded/failed/skipped |
| started_at / finished_at | DateTime | 可空 | 起止时间 |
| error_message | String(255) | 可空 | 失败原因 |

#### materials（物料主数据）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(32) | PK | 如 `MAT-001` |
| name | String(255) | 非空 | 物料名 |
| spec | String(255) | 可空 | 规格型号 |
| manufacturer | String(128) | 可空 | 厂商 |
| unit | String(32) | 可空 | 计量单位 |

#### samples（样品实例）— 扩现有表

现有字段保留：`code` / `name` / `batch` / `location` / `status` / `updated_at`。

| 字段 | 类型 | 变更 | 说明 |
|------|------|------|------|
| material_id | String(32) | 新增，FK→materials.id | 关联物料主数据（追溯批次） |

#### measurements（测量数据点）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK 自增 | — |
| experiment_id | String(32) | FK→experiments.id | 所属实验 |
| experiment_step_id | Integer | 可空，FK→experiment_steps.id | 由哪一步产生 |
| metric_name | String(64) | 非空 | 指标名（温度/压力/漏失量…） |
| metric_value | Float | 非空 | 数值 |
| unit | String(32) | 可空 | 单位 |
| timestamp | DateTime | 非空，索引 | 采集时间 |

#### device_telemetry_history — 复用（不动）

现有设备遥测表继续用于「设备级后台周期性采集」；「实验级数据点」走 measurements。二者不合并：telemetry 回答"设备一直在采什么"，measurements 回答"这次实验测到了什么"。若后续需将实验期间的遥测关联回实验，可在 telemetry 上加可空 `experiment_id`，本期不做。

---

## 2. M3 设备驱动层详细设计

### 2.1 DeviceDriver 抽象接口（签名）

```python
class DeviceDriver(ABC):
    device_id: str          # 关联 devices.id

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...

    # 同步阻塞式：引擎下发一步，驱动执行完成后返回结果
    async def execute_step(self, step: ExperimentStep) -> StepResult: ...

    # 遥测：与执行解耦，采集线程独立轮询
    async def read_telemetry(self) -> list[TelemetryPoint]: ...

    async def get_status(self) -> DeviceStatus: ...  # idle/busy/error/offline
    async def cancel(self) -> None: ...
```

### 2.2 关键类型

```python
class StepResult:
    success: bool
    status_code: str | None      # 失败时的错误码
    message: str                 # 结果描述

class TelemetryPoint:
    metric_name: str
    value: float
    unit: str | None
    timestamp: datetime

class DeviceStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
```

### 2.3 MockDriver（演示版）

- **状态机**：`idle → busy → idle`；`execute_step` 期间置 busy，完成或失败回到 idle；`cancel()` 强制回 idle 并标记异常。
- **剧本引擎**：核心是「动作解释器」，把 `action + params` 转成一段随时间演化的数据曲线。
  - 例：`{action:"set_temperature", params:{target:180, ramp_rate:2}}` → 按 2°C/s 爬坡，每个 tick（如 0.5s）更新内部温度并可供 `read_telemetry` 读取，到达 180 后返回 success。
  - 例：`{action:"hold", params:{duration_s:600}}` → 计时，期间维持当前值，超时返回 success。
- **设备行为库**：预置 HTHP 失水仪、天平、pH 计等型号的行为参数（爬坡速率、噪声幅度、量程），`MockDriver(device_id, behavior=...)` 实例化。
- **数据源**：`hardware_info/hardware_simulation_data.json`（HTHP 漏失量）作为第一条演示方案的曲线模板。

### 2.4 真实驱动（生产版，预留接口）

`SerialDriver`（RS232）/ `HttpDriver` / `GpibDriver` 实现同一 `DeviceDriver` 接口。上层引擎零改动即可切换。

---

## 3. M2 编排引擎详细设计

### 3.1 实验级状态机

| 状态 | 含义 | 进入条件 | 离开动作 |
|------|------|---------|---------|
| draft 草稿 | 已创建未就绪 | create | 校验通过 → ready |
| ready 待执行 | 就绪可启动 | 步骤展开完成 | start → running |
| running 执行中 | 步骤推进中 | start | 全部步骤完成 → completed；步骤失败 → failed；人工中止 → aborted |
| completed 完成 | 正常完成 | 全部步骤 succeeded | — |
| failed 异常 | 步骤失败待介入 | 某步 failed | 介入后回 running / 或 aborted |
| aborted 中止 | 人工中止 | 人工操作 | — |

**running 阶段相位（phase）**：`preparing 备料 → executing 执行 → collecting 数据采集`，对应顶层设计的"备料→执行中→数据采集"。相位只用于界面展示与日志，不参与状态机转换。

### 3.2 步骤动作表（action 枚举）

| action | 含义 | 典型 params |
|--------|------|------------|
| load_sample | 装样 | `{sample_code}` |
| set_temperature | 设定温度 | `{target, ramp_rate?}` |
| hold | 恒温/恒压保持 | `{duration_s}` |
| measure | 采一个测量点 | `{metric_name}` |
| ramp | 按速率变化 | `{target, rate}` |
| drain | 排空/卸压 | `{}` |
| report | 生成报告 | `{}` |

### 3.3 完成判据（complete_criteria）

| type | 含义 | 附加字段 |
|------|------|---------|
| target_reached | 达到目标值 | `{target, tolerance}` |
| hold_duration | 保持时长 | `{duration_s}` |
| measurement_count | 采满 N 个点 | `{count}` |

### 3.4 引擎类设计

```python
class Orchestrator:
    def __init__(self, driver_registry: DriverRegistry, repo: ExperimentRepository): ...

    async def create_experiment(self, protocol_id, operator_id, sample_code) -> Experiment
    async def start(self, experiment_id) -> None        # 展开步骤 + 启动状态机
    async def retry_step(self, experiment_id, step_order) -> None
    async def skip_step(self, experiment_id, step_order) -> None
    async def abort(self, experiment_id) -> None
    async def get_progress(self, experiment_id) -> ProgressSnapshot
```

### 3.5 步骤展开逻辑（start 时）

1. 读 `experiments` → 拿 `protocol_id` → 读 `protocol_steps`（按 step_order 排序）。
2. 逐条实例化为 `experiment_steps`：把模板 params 与实验参数（样品、目标值）合并，写库，状态 pending。
3. 校验设备占用：目标设备若被其他运行中实验占用 → 该实验保持 ready，等待设备释放（或直接报错，见待决策）。
4. 状态机推进：ready → running，进入主循环。

### 3.6 主循环（每个实验一个后台任务）

```
while 有未完成步骤:
    取当前步骤 → 置 running → 通过 DriverRegistry 拿到对应 DeviceDriver
    → driver.execute_step(step)（阻塞等待）
    → 成功：步骤 succeeded，推进下一步
    → 失败：实验 failed，冻结现场（不释放已完成数据），等待人工介入
    每步状态变化 → 发 SSE 事件
全部完成 → 实验 completed
```

### 3.7 异常恢复

- **冻结现场**：失败时保留当前步骤参数、已完成步骤、已写数据点；设备占用状态保留，介入期间实验不自动推进。
- **三个介入动作**：`retry_step`（重跑当前步）、`skip_step`（标记 skipped 继续）、`abort`（释放设备，保留已采数据）。
- **原则**：介入不触发任何数据回滚。

### 3.8 DriverRegistry（设备占用管理）

```python
class DriverRegistry:
    async def acquire(self, device_id, experiment_id) -> DeviceDriver  # 占用，冲突抛 BusyError
    async def release(self, device_id) -> None
```

设备同时只服务一个实验；冲突时该实验入队等待（演示版可简化为直接报"设备忙"）。

---

## 4. M6 数据采集详细设计

- **设备级遥测**：复用 `HardwareCollectorService` 后台循环，周期读各驱动 `read_telemetry()` 写 `device_telemetry_history`。
- **实验级数据点**：在 M2 步骤执行 `measure` 动作时，把读数写 `measurements`（关联 experiment_id + experiment_step_id）。真实感曲线来自 MockDriver 剧本引擎的连续 tick，而非一次性写入。
- **曲线数据**：前端从 `measurements` 按 experiment_id + metric_name 拉取时间序列，用于实验工作台实时曲线。
- 生产版替换：真实驱动按协议轮询/推送读数，其余入库逻辑不变。

---

## 5. M5 交互层详细设计

### 5.1 REST API 端点（实验域新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/protocols` | 方案库列表 |
| GET | `/api/v1/protocols/{id}` | 方案详情（含步骤模板） |
| POST | `/api/v1/experiments` | 创建实验（选方案 + 操作员 + 样品） |
| POST | `/api/v1/experiments/{id}/start` | 启动实验 |
| GET | `/api/v1/experiments/{id}` | 实验详情（状态 + 步骤 + 追溯链） |
| GET | `/api/v1/experiments/{id}/progress` | 进度快照 |
| GET | `/api/v1/experiments/{id}/measurements` | 测量数据（时间序列） |
| POST | `/api/v1/experiments/{id}/retry-step` | 重试步骤 |
| POST | `/api/v1/experiments/{id}/skip-step` | 跳过步骤 |
| POST | `/api/v1/experiments/{id}/abort` | 中止实验 |
| GET | `/api/v1/experiments` | 实验列表（看板用） |
| GET | `/api/v1/dashboard` | 看板聚合（设备状态/进度/统计） |

### 5.2 Agent 实验域工具（基于 function calling）

在 `ToolManager` 注册以下工具，复用现有 `list_tools_schema()` 与 `chat_with_tools` 循环：

| 工具名 | 参数 | 作用 |
|--------|------|------|
| `create_experiment` | protocol_id, sample_code | 创建实验 |
| `start_experiment` | experiment_id | 启动 |
| `query_experiment_progress` | experiment_id | 查进度 |
| `query_experiment_result` | experiment_id | 查结果/数据 |
| `list_protocols` | — | 列出方案 |

Agent 工具内部调用 M2 的 `Orchestrator`，与 Web API 共享同一套后端能力；LLM 不进执行主链路，只做"自然语言 → 工具调用"的入口。

### 5.3 前端页面

- 新增 Tab：**实验看板**（管理者）、**方案库**、**实验工作台**（启动 + 实时进度 + 曲线）、**实验追溯**（详情）。
- 现有 5 个 Tab（对话/文件/硬件/数据/网页填表）保留为辅助工作台。
- 硬件 Tab 数据源改为读 M3 驱动层 `read_telemetry()`，不再各自随机漂移。

---

## 6. M7 审计追溯详细设计

- **审计事件模型**：扩展现有 `tool_audits` 为通用审计表，或新增 `experiment_audits`（事件类型：create/start/step_succeed/step_fail/retry/skip/abort/complete）。
- **追溯查询**：给定 experiment_id，一次拉出完整链条——方案版本、操作员、设备、样品→物料、步骤执行明细（experiment_steps）、数据点（measurements）、异常记录。
- **增强**：导出报告（实验室质量体系格式），后续做。

---

## 7. M4 管理系统对接详细设计

- **抽象接口**（本期只定义，不实现）：

```python
class LimsAdapter(ABC):
    async def pull_protocols(self) -> list[Protocol]       # 拉取实验设计
    async def pull_master_data(self) -> None               # 人员/物料主数据
    async def push_results(self, experiment_id) -> None    # 回传结果
```

- **演示版**：预置方案（种子数据）即 Mock 源，LimsAdapter 用 `MockLimsAdapter` 占位，返回种子数据。
- **生产版**：`RestLimsAdapter`（或文件/DB 直连），增量同步 + 冲突处理，协议待接触目标 LIMS 后定。

---

## 8. SSE 事件规范

实验进度事件沿用现有 SSE 机制，新增实验域事件类型：

| type | data 字段 | 触发时机 |
|------|----------|---------|
| experiment_status | `{experiment_id, status, phase}` | 状态/相位变化 |
| step_status | `{experiment_id, step_order, status, action, error?}` | 步骤状态变化 |
| measurement | `{experiment_id, metric_name, value, unit, timestamp}` | 新数据点 |

前端与 Agent 对话共用此事件流；对话已有的 `tools/chunk/chart/done` 事件保持不变。

---

## 9. 与现有代码的落点对照

| 详细设计项 | 落点 |
|-----------|------|
| M1 表结构 | `app/models/tables.py` 扩表 + Alembic 迁移 |
| M2 编排引擎 | 新建 `app/services/orchestrator.py`（或 `app/agent` 之外的独立模块） |
| M3 驱动 | 新建 `app/hardware/drivers/`，重构 `hardware_tools.py` 的 Mock 数据 |
| M5 API | `app/api/v1/endpoints/experiments.py` 新增 |
| M5 Agent 工具 | `app/tools/builtin/experiment_tools.py` 新增 |
| M6 采集 | 复用 `hardware_collector.py` + 新增 measurements 写入 |
| M7 审计 | 扩展 `tool_audits` 或新增实验审计表 |
| M4 对接 | `app/services/lims_adapter.py` 预留接口 |

---

## 待决策（实现前需确认）

1. 设备冲突策略：演示版是「入队等待」还是「直接报错」？（推荐演示版直接报"设备忙"，更直观）
2. 一条实验是否允许关联多个样品/多台设备？（推荐演示版单样品，设备通过步骤表达，避免过早复杂化）
3. 现有 `experiments.operator` 字符串字段：是彻底迁移为 `operator_id` 外键，还是过渡期双轨（推荐彻底迁移，一次性干净）。
