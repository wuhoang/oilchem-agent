# OilChem Agent — API

All business endpoints are versioned under `/api/v1`. Bootstrap endpoints
remain at the root.

> **v1.3.0 认证**：`AUTH_ENABLED=true` 时，除 `POST /api/v1/auth/login` 与
> `GET /api/v1/experiments/events`（走 `?token=`）外，所有 `/api/v1/*`
> 端点需携带 `Authorization: Bearer <token>` 请求头；401 表示未登录或令牌过期。

## Bootstrap endpoints

### `GET /`

Returns the application banner.

```json
{
  "name": "OilChem Agent",
  "version": "1.3.0",
  "status": "running"
}
```

### `GET /health`

Liveness probe.

```json
{ "status": "ok" }
```

## v1 endpoints

### 认证

| Method | Path                  | Description                             |
|--------|-----------------------|-----------------------------------------|
| POST   | `/api/v1/auth/login`  | 账号密码登录，签发 JWT 令牌（默认 7 天） |
| GET    | `/api/v1/auth/me`     | 当前登录用户 + 认证开关（未登录时 user 为 null，不抛 401） |

#### `POST /api/v1/auth/login`

请求体：`{"username": "admin", "password": "admin123"}`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": { "id": 1, "username": "admin", "role": "admin" }
}
```

#### `GET /api/v1/auth/me`

```json
{
  "user": { "id": 1, "username": "admin", "role": "admin", "email": "admin@oilchem.local" },
  "auth_enabled": true
}
```

演示账号（users 表为空时自动创建）：`admin` / `operator` / `reviewer`，
密码默认 `admin123` / `operator123` / `reviewer123`，可用 `.env` 中
`AUTH_ADMIN_PASSWORD` / `AUTH_OPERATOR_PASSWORD` / `AUTH_REVIEWER_PASSWORD` 覆盖。

### LLM 管理

| Method | Path                | Description                |
|--------|---------------------|----------------------------|
| GET    | `/api/v1/llm/test`  | LLM 连通性测试             |
| GET    | `/api/v1/llm/info`  | 获取 LLM 配置信息          |

#### `GET /api/v1/llm/test`

测试 LLM 连通性，发送一条简短消息验证模型是否可正常调用。

```json
{
  "success": true,
  "message": "Connected. Response: OK",
  "latency_ms": 1234,
  "model": "deepseek-chat"
}
```

#### `GET /api/v1/llm/info`

获取当前 LLM 配置信息（不含敏感字段如 API Key）。

```json
{
  "provider": "openai",
  "base_url": "https://api.deepseek.com/v1",
  "model_name": "deepseek-chat",
  "timeout": 30.0
}
```

### Agent 对话

| Method | Path                          | Description                |
|--------|-------------------------------|----------------------------|
| POST   | `/api/v1/chat`                | Agent 同步对话             |
| POST   | `/api/v1/chat/stream`         | Agent SSE 流式对话         |
| GET    | `/api/v1/chat/sessions`       | 列出所有会话               |
| GET    | `/api/v1/chat/sessions/{id}`  | 获取会话详情               |
| DELETE | `/api/v1/chat/sessions/{id}`  | 删除会话                   |

#### `POST /api/v1/chat`

请求体：
```json
{
  "session_id": null,
  "message": "读取 C:/data/report.csv 并分析数据",
  "system_prompt": null,
  "temperature": null
}
```

响应：
```json
{
  "session_id": "abc123",
  "response": "以下是 report.csv 的分析结果...",
  "plan_used": true,
  "plan_steps": 2,
  "success": true,
  "error": null,
  "execution_time_ms": 5234
}
```

#### `POST /api/v1/chat/stream`

SSE 流式对话端点，逐块推送响应。

### 文件管理

| Method | Path                          | Description                |
|--------|-------------------------------|----------------------------|
| POST   | `/api/v1/files/read`          | 读取文件内容               |
| POST   | `/api/v1/files/write`         | 写入文件（覆盖）           |
| POST   | `/api/v1/files/append`        | 追加内容到文件             |
| POST   | `/api/v1/files/list`          | 列出目录内容               |
| POST   | `/api/v1/files/delete`        | 删除文件                   |
| GET    | `/api/v1/files/tools`         | 列出可用工具               |
| POST   | `/api/v1/files/watch/start`   | 启动文件监听               |
| POST   | `/api/v1/files/watch/stop`    | 停止文件监听               |
| WS     | `/ws/files/events`            | 文件变化事件推送           |

#### `POST /api/v1/files/read`

请求体：
```json
{
  "path": "C:/data/report.csv",
  "start_line": 1,
  "end_line": 10
}
```

响应：
```json
{
  "success": true,
  "data": {
    "path": "C:/data/report.csv",
    "content": "...",
    "total_lines": 100,
    "read_lines": 10
  },
  "error": null
}
```

#### `WS /ws/files/events`

WebSocket 连接，接收文件变化事件推送。

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

### 网页操作

| Method | Path                          | Description                |
|--------|-------------------------------|----------------------------|
| POST   | `/api/v1/web/browse`          | 浏览网页（内容+表单+截图） |
| POST   | `/api/v1/web/smart-fill`      | 智能填表（登录+字段映射）  |
| POST   | `/api/v1/web/fill-form`       | 按索引精确填表             |
| POST   | `/api/v1/web/extract-text`    | 提取网页文本               |

### 硬件设备

| Method | Path                                  | Description                |
|--------|---------------------------------------|----------------------------|
| GET    | `/api/v1/hardware/devices`            | 列出所有设备（DriverRegistry 统一源，6 台油化仿真设备） |
| GET    | `/api/v1/hardware/devices/{id}`       | 获取单个设备详情           |
| POST   | `/api/v1/hardware/devices/{id}/command` | 下发设备指令             |

### 数据管理

| Method | Path                          | Description                |
|--------|-------------------------------|----------------------------|
| GET    | `/api/v1/db/tables`           | 列出业务表                 |
| POST   | `/api/v1/db/{table}/query`    | 查询表数据                 |
| POST   | `/api/v1/db/{table}/insert`   | 插入一行                   |
| POST   | `/api/v1/db/{table}/update`   | 更新一行                   |
| DELETE | `/api/v1/db/{table}/delete`   | 删除一行                   |

### 实验域（M1-M7）

#### 方案库

| Method | Path                          | Description                |
|--------|-------------------------------|----------------------------|
| GET    | `/api/v1/protocols`           | 列出实验方案               |
| GET    | `/api/v1/protocols/{id}`      | 方案详情（含步骤模板）     |

#### 实验生命周期

| Method | Path                                      | Description                |
|--------|-------------------------------------------|----------------------------|
| GET    | `/api/v1/experiments`                     | 实验列表（看板）           |
| POST   | `/api/v1/experiments`                     | 创建实验                   |
| GET    | `/api/v1/experiments/{id}`                | 实验详情（步骤+追溯链+报告） |
| POST   | `/api/v1/experiments/{id}/start`          | 启动实验（展开步骤+复位设备） |
| GET    | `/api/v1/experiments/{id}/progress`       | 进度快照                   |
| GET    | `/api/v1/experiments/{id}/measurements`   | 测量数据（时间序列）       |
| GET    | `/api/v1/experiments/{id}/report`         | 报告文件清单（Word+Excel） |
| POST   | `/api/v1/experiments/{id}/retry-step`     | 重试失败步骤               |
| POST   | `/api/v1/experiments/{id}/skip-step`      | 跳过失败步骤               |
| POST   | `/api/v1/experiments/{id}/abort`          | 中止实验                   |
| POST   | `/api/v1/experiments/{id}/approve`        | 审核通过（待审核→已完成），需 reviewer/admin 角色 |
| POST   | `/api/v1/experiments/{id}/reject`         | 审核驳回（待审核→已驳回），需 reviewer/admin 角色 |

#### 实验员 & 看板 & 事件

| Method | Path                          | Description                |
|--------|-------------------------------|----------------------------|
| GET    | `/api/v1/experimenters`       | 实验员列表                 |
| GET    | `/api/v1/reviewers`           | 可选审核人列表（users 表 reviewer/admin 角色账号） |
| GET    | `/api/v1/dashboard`           | 看板聚合（设备/进度/统计） |
| GET    | `/api/v1/experiments/events`  | SSE 实验事件流（status/step/measurement），AUTH 开启时需 `?token=` |

#### `POST /api/v1/experiments`（创建实验）

请求体：
```json
{
  "name": "HTHP 滤失量测试",
  "protocol_id": "PROTO-001",
  "operator_id": "OP-001",
  "sample_code": "S-2026-0801"
}
```

响应：
```json
{ "id": "EXP-ABC123", "name": "HTHP 滤失量测试", "status": "草稿" }
```

#### `GET /api/v1/experiments/{id}`（实验详情）

响应含 `experiment`（含 `result` JSON 摘要+图表、`report_path`、审核字段 `reviewed_by`/`reviewed_by_id`/`reviewed_at`/`review_comment`）、`steps`（步骤执行明细）、`audits`（审计时间线）。
