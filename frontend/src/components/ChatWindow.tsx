/**
 * 主对话窗口组件。
 *
 * 协调消息列表、输入框和 API 调用，管理对话状态。
 * 支持规划过程展示、工具调用可视化、真正的 LLM 流式输出。
 * 支持 localStorage 持久化，切换 Tab 不丢失聊天记录。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChartData, ChatMessage, StreamEvent } from "../types";
import { sendChatMessageStream } from "../services/api";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { notifyError } from "./ErrorToast";

interface ChatWindowProps {
  sessionId: string | null;
  onSessionCreated: (sessionId: string) => void;
  onMessageComplete?: () => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const STORAGE_KEY = "oilchem:chat:messages";

function loadMessagesFromStorage(sessionId: string | null): ChatMessage[] {
  if (!sessionId) return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const all: Record<string, ChatMessage[]> = JSON.parse(raw);
    return all[sessionId] || [];
  } catch {
    return [];
  }
}

function saveMessagesToStorage(sessionId: string | null, messages: ChatMessage[]) {
  if (!sessionId) return;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const all: Record<string, ChatMessage[]> = raw ? JSON.parse(raw) : {};
    all[sessionId] = messages;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    // ignore quota errors
  }
}

function removeSessionFromStorage(sessionId: string) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const all: Record<string, ChatMessage[]> = JSON.parse(raw);
    delete all[sessionId];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    // ignore
  }
}

export function ChatWindow({ sessionId, onSessionCreated, onMessageComplete }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    loadMessagesFromStorage(sessionId)
  );
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef(sessionId);
  const onSessionCreatedRef = useRef(onSessionCreated);
  const prevSessionIdRef = useRef<string | null>(null);
  const messagesRef = useRef(messages);

  sessionIdRef.current = sessionId;
  onSessionCreatedRef.current = onSessionCreated;
  messagesRef.current = messages;
  const onMessageCompleteRef = useRef(onMessageComplete);
  onMessageCompleteRef.current = onMessageComplete;

  // 保存消息到 localStorage（防抖）
  useEffect(() => {
    const timer = setTimeout(() => {
      saveMessagesToStorage(sessionIdRef.current, messages);
    }, 300);
    return () => clearTimeout(timer);
  }, [messages, sessionId]);

  const handleSend = useCallback(
    async (text: string) => {
      if (loading) return;

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };

      const assistantMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        streaming: true,
        toolCalls: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setLoading(true);

      abortRef.current = new AbortController();

      try {
        let accumulated = "";
        let newSessionId = sessionIdRef.current;

        const updateAssistant = (updater: (msg: ChatMessage) => ChatMessage) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsg.id ? updater(m) : m))
          );
        };

        const persistMessages = (sid: string | null) => {
          saveMessagesToStorage(sid, messagesRef.current);
        };

        await sendChatMessageStream(
          {
            session_id: sessionIdRef.current,
            message: text,
          },
          (event: StreamEvent) => {
            if (abortRef.current?.signal.aborted) return;
            switch (event.type) {
              case "tools": {
                const callIndex = event.data?.call_index as number;
                const action = event.data?.action as string;
                const toolName = event.data?.tool_name as string;
                const description = event.data?.description as string;

                if (action === "start") {
                  updateAssistant((m) => {
                    const calls = [...(m.toolCalls || [])];
                    // 按 call_index 更新，不存在则追加
                    const idx = calls.findIndex((c) => c.call_index === callIndex);
                    if (idx >= 0) {
                      calls[idx] = { ...calls[idx], status: "running" };
                    } else {
                      calls.push({
                        call_index: callIndex,
                        tool_name: toolName || null,
                        description: description || `工具调用 ${callIndex}`,
                        status: "running",
                      });
                    }
                    return { ...m, toolCalls: calls };
                  });
                } else if (action === "complete") {
                  const result = (event.data?.output || event.data?.result) as string;
                  const success = event.data?.success as boolean;
                  updateAssistant((m) => {
                    const calls = [...(m.toolCalls || [])];
                    const idx = calls.findIndex((c) => c.call_index === callIndex);
                    if (idx >= 0) {
                      calls[idx] = {
                        ...calls[idx],
                        status: success ? "success" : "error",
                        result: result ? String(result).slice(0, 100) : undefined,
                      };
                    }
                    return { ...m, toolCalls: calls };
                  });
                }
                break;
              }

              case "thinking": {
                const content = event.content || "";
                const planGoal = event.data?.plan_goal as string;
                const planSteps = event.data?.plan_steps as number;
                updateAssistant((m) => ({
                  ...m,
                  thinking: content || `💭 正在思考...${planGoal ? `\n🎯 ${planGoal}` : ""}${planSteps ? `\n📋 ${planSteps} 个步骤` : ""}`,
                }));
                break;
              }

              case "chunk": {
                if (event.content) {
                  accumulated += event.content;
                  updateAssistant((m) => ({ ...m, content: accumulated }));
                }
                break;
              }

              case "chart": {
                const chartData = event.data as unknown as ChartData;
                if (chartData?.image_base64) {
                  updateAssistant((m) => ({
                    ...m,
                    charts: [...(m.charts || []), chartData],
                  }));
                }
                break;
              }

              case "done": {
                if (event.session_id && event.session_id !== newSessionId) {
                  newSessionId = event.session_id;
                  sessionIdRef.current = event.session_id;
                  onSessionCreatedRef.current(event.session_id);
                  // 将之前用 null key 存储的消息迁移到正确的 session id
                  const currentMsgs = messagesRef.current;
                  saveMessagesToStorage(event.session_id, currentMsgs);
                  removeSessionFromStorage("null");
                }
                setMessages((prev) =>
                  prev.map((m) => {
                    if (m.id !== assistantMsg.id) return m;
                    return {
                      ...m,
                      content: event.content || accumulated,
                      streaming: false,
                    };
                  })
                );
                // 最终保存
                persistMessages(newSessionId);
                // 通知父组件刷新侧边栏
                onMessageCompleteRef.current?.();
                break;
              }

              case "error": {
                notifyError(event.content || "对话发生未知错误");
                updateAssistant((m) => ({
                  ...m,
                  content: `❌ ${event.content || "未知错误"}`,
                  streaming: false,
                }));
                break;
              }
            }
          },
          abortRef.current?.signal,
        );
      } catch (err) {
        if ((err instanceof Error && err.name === "AbortError") || abortRef.current?.signal.aborted) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    streaming: false,
                  }
                : m
            )
          );
        } else {
          const errMsg = err instanceof Error ? err.message : String(err);
          notifyError(`请求失败：${errMsg}`);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    content: `❌ 请求失败：${errMsg}`,
                    streaming: false,
                  }
                : m
            )
          );
        }
      } finally {
        setLoading(false);
        abortRef.current = null;
      }
    },
    [loading],
  );

  useEffect(() => {
    const prev = prevSessionIdRef.current;
    if (prev !== sessionId) {
      // 切换会话时从 localStorage 加载历史消息
      setMessages(loadMessagesFromStorage(sessionId));
    }
    prevSessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      handleSend(customEvent.detail);
    };
    window.addEventListener("oilchem:quick-prompt", handler);
    return () => window.removeEventListener("oilchem:quick-prompt", handler);
  }, [handleSend]);

  const handleStop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  };

  return (
    <div className="flex h-full flex-1 flex-col bg-slate-50">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold text-slate-700">
            {sessionId ? `会话 ${sessionId.slice(-8)}` : "新会话"}
          </h1>
          <span className="text-xs text-slate-400">
            {messages.length} 条消息
          </span>
          {loading && (
            <span className="flex items-center gap-1 rounded-full bg-blue-100 px-3 py-0.5 text-xs text-blue-600">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
              正在思考...
            </span>
          )}
        </div>

        {loading && (
          <button
            onClick={handleStop}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-100"
          >
            停止生成
          </button>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-hidden">
        <MessageList messages={messages} />
      </div>

      {/* Input */}
      <MessageInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
