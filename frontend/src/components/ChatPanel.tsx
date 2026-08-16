/**
 * ChatPanel — 常驻右侧聊天面板。
 *
 * 封装：会话列表 + ChatWindow + 折叠按钮。
 * 用户在任意功能页都能直接对话；context 由父组件传入（当前页面），
 * 后端据此加载对应的工具子集。
 */

import { useEffect, useState } from "react";
import type { SessionInfo } from "../types";
import { deleteSession, listSessions } from "../services/api";
import { ChatWindow } from "./ChatWindow";

interface ChatPanelProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  refreshKey?: number;
  onSessionCreated: (sessionId: string) => void;
  onMessageComplete?: () => void;
  /** 当前页面上下文（experiments/hardware/files/database/webform），透传给后端做工具路由 */
  context?: string;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function ChatPanel({
  currentSessionId,
  onSelectSession,
  onNewSession,
  refreshKey,
  onSessionCreated,
  onMessageComplete,
  context,
  collapsed,
  onToggleCollapsed,
}: ChatPanelProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await listSessions();
        if (!cancelled) {
          setSessions(res.sessions);
        }
      } catch {
        if (!cancelled) {
          setSessions([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("确定要删除这个会话吗？")) return;

    setDeleting(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        onNewSession();
      }
    } catch {
      // 忽略错误
    } finally {
      setDeleting(null);
    }
  };

  // 折叠态：只显示一个展开按钮窄条
  if (collapsed) {
    return (
      <aside className="flex w-10 shrink-0 flex-col items-center border-l border-slate-200 bg-white py-3">
        <button
          onClick={onToggleCollapsed}
          title="展开聊天面板"
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm transition hover:bg-blue-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-96 shrink-0 flex-col border-l border-slate-200 bg-slate-50">
      {/* 顶栏：折叠 + 标题 + 新建 */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleCollapsed}
            title="折叠聊天面板"
            className="flex h-7 w-7 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            </svg>
          </button>
          <span className="text-sm font-semibold text-slate-700">AI 助手</span>
        </div>
        <button
          onClick={onNewSession}
          className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white transition hover:bg-blue-700"
          title="新建会话"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* 会话列表（折叠摘要） */}
      <div className="max-h-44 shrink-0 overflow-y-auto border-b border-slate-200 bg-white p-2">
        {loading ? (
          <div className="flex items-center justify-center py-4 text-xs text-slate-400">
            加载中...
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex items-center justify-center gap-1 py-4 text-xs text-slate-400">
            📭 暂无会话
          </div>
        ) : (
          <ul className="space-y-1">
            {sessions.map((session) => (
              <li key={session.session_id}>
                <button
                  onClick={() => onSelectSession(session.session_id)}
                  className={
                    "group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition " +
                    (currentSessionId === session.session_id
                      ? "bg-blue-100 text-blue-700"
                      : "text-slate-600 hover:bg-slate-100")
                  }
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate">
                      {session.title || "会话 " + session.session_id.slice(-6)}
                    </p>
                  </div>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => handleDelete(session.session_id, e)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleDelete(session.session_id, e as unknown as React.MouseEvent);
                      }
                    }}
                    aria-disabled={deleting === session.session_id}
                    className="hidden h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded text-slate-400 transition hover:bg-red-100 hover:text-red-500 group-hover:flex disabled:opacity-50"
                    title="删除"
                  >
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 聊天区 */}
      <div className="flex min-h-0 flex-1 flex-col">
        <ChatWindow
          sessionId={currentSessionId}
          onSessionCreated={onSessionCreated}
          onMessageComplete={onMessageComplete}
          context={context}
        />
      </div>
    </aside>
  );
}
