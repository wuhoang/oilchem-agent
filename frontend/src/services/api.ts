/**
 * API 服务层。
 *
 * 封装所有与后端 API 的交互，包括：
 * - 对话接口（同步 + 流式 SSE）
 * - 会话管理（CRUD）
 * - LLM 配置查询
 * - 文件操作（读取、写入、列表）
 */

import type {
  ChatRequest,
  ChatResponse,
  FileListResponse,
  FilePreviewResponse,
  FileReadResponse,
  LLMInfo,
  SessionInfo,
  StreamEvent,
  ToolInfo,
} from "../types";

const API_BASE = "/api/v1";

// ---------------------------------------------------------------------------
// 认证
// ---------------------------------------------------------------------------

const TOKEN_KEY = "oilchem_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** 401 时通知全局（App 负责跳登录页） */
function notifyAuthExpired(): void {
  setToken(null);
  window.dispatchEvent(new CustomEvent("auth:expired"));
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options.headers,
    },
    ...options,
  });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    notifyAuthExpired();
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export interface AuthUser {
  id: number;
  username: string;
  role: string;
  email?: string;
}

export async function login(
  username: string,
  password: string,
): Promise<AuthUser> {
  const res = await request<{ access_token: string; user: AuthUser }>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ username, password }),
    },
  );
  setToken(res.access_token);
  return res.user;
}

export async function fetchMe(): Promise<{
  user: AuthUser | null;
  auth_enabled: boolean;
}> {
  return request("/auth/me");
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export async function sendChatMessage(
  req: ChatRequest,
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function sendChatMessageStream(
  req: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${API_BASE}/chat/stream`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(req),
    signal,
  });

  if (res.status === 401) {
    notifyAuthExpired();
  }

  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed: HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;

      const jsonStr = trimmed.slice(5).trim();
      if (!jsonStr) continue;

      try {
        const event = JSON.parse(jsonStr) as StreamEvent;
        onEvent(event);
      } catch {
        // Ignore non-JSON lines
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export async function listSessions(): Promise<{ sessions: SessionInfo[] }> {
  return request<{ sessions: SessionInfo[] }>("/chat/sessions");
}

export async function getSession(
  sessionId: string,
): Promise<SessionInfo> {
  return request<SessionInfo>(`/chat/sessions/${encodeURIComponent(sessionId)}`);
}

export async function deleteSession(
  sessionId: string,
): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(
    `/chat/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
}

// ---------------------------------------------------------------------------
// LLM
// ---------------------------------------------------------------------------

export async function testLLM(): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>("/llm/test");
}

export async function getLLMInfo(): Promise<LLMInfo> {
  return request<LLMInfo>("/llm/info");
}

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export async function listFiles(
  path: string,
  recursive = false,
  pattern?: string,
): Promise<FileListResponse> {
  const res = await request<{ success: boolean; data: FileListResponse }>("/files/list", {
    method: "POST",
    body: JSON.stringify({ path, recursive, pattern }),
  });
  return res.data;
}

export async function readFile(
  path: string,
  startLine?: number,
  endLine?: number,
): Promise<FileReadResponse> {
  const body: Record<string, unknown> = { path };
  if (startLine) body.start_line = startLine;
  if (endLine) body.end_line = endLine;
  const res = await request<{ success: boolean; data: FileReadResponse }>("/files/read", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function previewFile(
  path: string,
): Promise<FilePreviewResponse> {
  return request<FilePreviewResponse>("/files/preview", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export async function writeFile(
  path: string,
  content: string,
): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>("/files/write", {
    method: "POST",
    body: JSON.stringify({ path, content }),
  });
}

export async function deleteFile(
  path: string,
): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>("/files/delete", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export async function listTools(): Promise<{ tools: ToolInfo[] }> {
  return request<{ tools: ToolInfo[] }>("/files/tools");
}

// ---------------------------------------------------------------------------
// Database (业务表 CRUD)
// ---------------------------------------------------------------------------

export interface DbTableInfo {
  name: string;
  count: number;
}

export interface DbQueryResult {
  success: boolean;
  table: string;
  data: Record<string, unknown>[];
  message: string;
}

export async function fetchDbTables(): Promise<{ tables: DbTableInfo[] }> {
  return request<{ tables: DbTableInfo[] }>("/db/tables");
}

export async function queryDbTable(
  table: string,
  q?: string,
  limit = 200,
): Promise<DbQueryResult> {
  return request<DbQueryResult>(`/db/${encodeURIComponent(table)}/query`, {
    method: "POST",
    body: JSON.stringify({ q: q || null, limit }),
  });
}

export async function insertDbRow(
  table: string,
  row: Record<string, unknown>,
): Promise<DbQueryResult> {
  return request<DbQueryResult>(`/db/${encodeURIComponent(table)}/insert`, {
    method: "POST",
    body: JSON.stringify({ row }),
  });
}

export async function updateDbRow(
  table: string,
  row: Record<string, unknown>,
): Promise<DbQueryResult> {
  return request<DbQueryResult>(`/db/${encodeURIComponent(table)}/update`, {
    method: "POST",
    body: JSON.stringify({ row }),
  });
}

export async function deleteDbRow(
  table: string,
  idValue: string,
): Promise<DbQueryResult> {
  return request<DbQueryResult>(
    `/db/${encodeURIComponent(table)}/delete?id_value=${encodeURIComponent(idValue)}`,
    { method: "DELETE" },
  );
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return fetch("/health").then((r) => r.json());
}

// ---------------------------------------------------------------------------
// Web Operations
// ---------------------------------------------------------------------------

export async function browseWeb(
  url: string,
  timeout = 30000,
): Promise<{ success: boolean; data?: any; error?: string }> {
  return request<{ success: boolean; data?: any; error?: string }>("/web/browse", {
    method: "POST",
    body: JSON.stringify({ url, timeout }),
  });
}

export async function fillWebForm(
  url: string,
  options: {
    username?: string;
    password?: string;
    formData?: Record<string, string>;
    submit?: boolean;
    timeout?: number;
  },
): Promise<{ success: boolean; data?: any; error?: string }> {
  const body: Record<string, any> = {
    url,
    timeout: options.timeout || 30000,
    submit: options.submit ?? true,
  };
  if (options.username) body.username = options.username;
  if (options.password) body.password = options.password;
  if (options.formData) body.form_data = options.formData;

  return request<{ success: boolean; data?: any; error?: string }>("/web/fill-form", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function smartFillForm(
  url: string,
  options: {
    username?: string;
    password?: string;
    fieldMapping?: Record<string, string>;
    autoSubmit?: boolean;
    timeout?: number;
  },
): Promise<{ success: boolean; data?: any; error?: string }> {
  const body: Record<string, any> = {
    url,
    timeout: options.timeout || 30000,
    auto_submit: options.autoSubmit ?? true,
  };
  if (options.username) body.username = options.username;
  if (options.password) body.password = options.password;
  if (options.fieldMapping) body.field_mapping = options.fieldMapping;

  return request<{ success: boolean; data?: any; error?: string }>("/web/smart-fill", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function extractWebText(
  url: string,
  selector?: string,
  timeout = 30000,
): Promise<{ success: boolean; data?: any; error?: string }> {
  const body: Record<string, any> = { url, timeout };
  if (selector) body.selector = selector;
  return request<{ success: boolean; data?: any; error?: string }>("/web/extract-text", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// 实验域（M5）
// ---------------------------------------------------------------------------

export interface Protocol {
  id: string;
  name: string;
  description?: string;
  version?: string;
  status?: string;
}

export interface Experiment {
  id: string;
  name: string;
  status: string;
  operator?: string;
  protocol_id?: string;
  protocol_name?: string;
  sample_code?: string;
  result?: string;
  report_path?: string;
  reviewed_by?: string;
  reviewed_by_id?: string;
  reviewed_at?: string;
  review_comment?: string;
}

export interface ExperimentStep {
  step_order: number;
  device_id: string;
  action: string;
  status: string;
  error?: string | null;
}

export interface AuditEvent {
  event_type: string;
  detail: string;
  created_at?: string | null;
}

export interface ExperimentDetail {
  experiment: Experiment;
  steps: ExperimentStep[];
  audits?: AuditEvent[];
}

export interface Experimenter {
  id: string;
  name: string;
  role: string;
  department?: string;
}

/** 审核人（users 表账号，数字 ID，与实验员的字符串 ID 不同） */
export interface Reviewer {
  id: number;
  name: string;
  role: string;
}

export interface Measurement {
  metric_name: string;
  value: number;
  unit?: string | null;
  timestamp?: string | null;
}

export async function fetchProtocols(): Promise<{ protocols: Protocol[] }> {
  return request<{ protocols: Protocol[] }>("/protocols");
}

export async function fetchExperiments(): Promise<{ experiments: Experiment[] }> {
  return request<{ experiments: Experiment[] }>("/experiments");
}

export async function createExperiment(payload: {
  name: string;
  protocol_id: string;
  operator_id: string;
  sample_code?: string;
}): Promise<{ id: string; name: string; status: string }> {
  return request("/experiments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function startExperiment(experimentId: string): Promise<{ success: boolean; message: string }> {
  return request(`/experiments/${encodeURIComponent(experimentId)}/start`, { method: "POST" });
}

export async function abortExperiment(experimentId: string): Promise<{ success: boolean; message: string }> {
  return request(`/experiments/${encodeURIComponent(experimentId)}/abort`, { method: "POST" });
}

export async function approveExperiment(experimentId: string, reviewerId: string, comment: string): Promise<{ success: boolean; message: string }> {
  return request(`/experiments/${encodeURIComponent(experimentId)}/approve`, {
    method: "POST",
    body: JSON.stringify({ reviewer_id: reviewerId, comment }),
  });
}

export async function rejectExperiment(experimentId: string, reviewerId: string, comment: string): Promise<{ success: boolean; message: string }> {
  return request(`/experiments/${encodeURIComponent(experimentId)}/reject`, {
    method: "POST",
    body: JSON.stringify({ reviewer_id: reviewerId, comment }),
  });
}

export async function fetchExperimentDetail(experimentId: string): Promise<ExperimentDetail> {
  return request<ExperimentDetail>(`/experiments/${encodeURIComponent(experimentId)}`);
}

export async function fetchExperimentMeasurements(experimentId: string): Promise<{ measurements: Measurement[] }> {
  return request<{ measurements: Measurement[] }>(`/experiments/${encodeURIComponent(experimentId)}/measurements`);
}

export async function fetchDashboard(): Promise<{ total_experiments: number; status_count: Record<string, number>; running: string[] }> {
  return request("/dashboard");
}

// ---------------------------------------------------------------------------
// 硬件设备（统一设备源）
// ---------------------------------------------------------------------------

export interface HardwareMetric {
  name: string;
  value: number;
  unit?: string;
}

export interface HardwareDevice {
  id: string;
  name: string;
  type: string;
  status: "online" | "busy" | "offline" | "error";
  metrics: HardwareMetric[];
  error?: string;
}

export async function fetchHardwareDevices(): Promise<{ devices: HardwareDevice[] }> {
  return request<{ devices: HardwareDevice[] }>("/hardware/devices");
}

export async function fetchExperimenters(): Promise<{ experimenters: Experimenter[] }> {
  return request<{ experimenters: Experimenter[] }>("/experimenters");
}

export async function fetchReviewers(): Promise<{ reviewers: Reviewer[] }> {
  return request<{ reviewers: Reviewer[] }>("/reviewers");
}

export async function fetchExperimentReport(experimentId: string): Promise<{ success: boolean; word_path: string; excel_path: string }> {
  return request(`/experiments/${encodeURIComponent(experimentId)}/report`);
}
