# OilChem Agent — API

All business endpoints are versioned under `/api/v1`. Bootstrap endpoints
remain at the root.

## Bootstrap endpoints

### `GET /`

Returns the application banner.

```json
{
  "name": "OilChem Agent",
  "version": "0.17.0",
  "status": "running"
}
```

### `GET /health`

Liveness probe.

```json
{ "status": "ok" }
```

## v1 endpoints

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
