/**
 * 全局类型定义。
 *
 * 与后端 API 模型保持一致，涵盖对话、会话、消息等核心类型。
 */

/** 消息角色 */
export type MessageRole = "user" | "assistant" | "system";

/** 单条聊天消息 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  streaming?: boolean;
  thinking?: string;
  toolCalls?: ToolCallInfo[];
  charts?: ChartData[];
}

/** 工具调用信息（function calling 模式下按调用序号动态追加） */
export interface ToolCallInfo {
  call_index: number;
  tool_name: string | null;
  description: string;
  status: "running" | "success" | "error";
  result?: string;
}

/** 对话请求 */
export interface ChatRequest {
  session_id?: string | null;
  message: string;
  system_prompt?: string | null;
  temperature?: number | null;
  /** 当前页面上下文（experiments/hardware/files/database/webform），决定后端加载的工具子集 */
  context?: string | null;
}

/** 对话响应 */
export interface ChatResponse {
  session_id: string;
  response: string;
  plan_used: boolean;
  plan_steps: number;
  success: boolean;
  error: string | null;
  execution_time_ms: number;
}

/** 会话信息 */
export interface SessionInfo {
  session_id: string;
  message_count: number;
  has_summary: boolean;
  title?: string;
  created_at?: number;
  updated_at?: number;
}

/** 流式事件类型 */
export type StreamEventType =
  | "planning"
  | "tools"
  | "thinking"
  | "chunk"
  | "chart"
  | "done"
  | "error";

/** 图表数据 */
export interface ChartData {
  chart_type: string;
  image_base64: string;
  image_mime: string;
  width: number;
  height: number;
}

/** 流式事件 */
export interface StreamEvent {
  type: StreamEventType;
  content?: string;
  session_id?: string;
  response?: string;
  plan_used?: boolean;
  plan_steps?: number;
  success?: boolean;
  execution_time_ms?: number;
  message?: string;
  done?: boolean;
  data?: Record<string, unknown>;
}

/** LLM 配置信息 */
export interface LLMInfo {
  provider: string;
  model_name: string;
  base_url: string;
  connected: boolean;
}

/** 工具信息 */
export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

/** 文件条目 */
export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size_bytes: number;
  modified: number;
  error?: string;
}

/** 文件列表响应 */
export interface FileListResponse {
  path: string;
  total: number;
  entries: FileEntry[];
}

/** 文件读取响应 */
export interface FileReadResponse {
  path: string;
  content?: string;
  is_binary?: boolean;
  size_bytes?: number;
  total_lines?: number;
  read_lines?: number;
  message?: string;
}

/** 文件预览响应 */
export interface FilePreviewResponse {
  success: boolean;
  file_type: string;
  content: any;
  error?: string;
}
