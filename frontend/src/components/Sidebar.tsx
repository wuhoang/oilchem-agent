/**
 * 会话侧边栏组件。
 *
 * 显示所有历史会话，支持新建、切换和删除。
 */

import { useEffect, useState } from "react";
import type { SessionInfo } from "../types";
import { deleteSession, listSessions } from "../services/api";

interface SidebarProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  refreshKey?: number;
}

export function Sidebar({
  currentSessionId,
  onSelectSession,
  onNewSession,
  refreshKey,
}: SidebarProps) {
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

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-slate-50">
      {/* 头部 Logo + 新建按钮 */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-teal-500 text-sm font-bold text-white">
            OC
          </div>
          <span className="text-sm font-semibold text-slate-700">
            OilChem Agent
          </span>
        </div>
        <button
          onClick={onNewSession}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white transition hover:bg-blue-700"
          title="新建会话"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4v16m8-8H4"
            />
          </svg>
        </button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="flex items-center justify-center py-8 text-sm text-slate-400">
            加载中...
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-sm text-slate-400">
            <div className="text-3xl">📭</div>
            <p>暂无会话</p>
            <p className="text-xs">点击 + 新建一个</p>
          </div>
        ) : (
          <ul className="space-y-1">
            {sessions.map((session) => (
              <li key={session.session_id}>
                <button
                  onClick={() => onSelectSession(session.session_id)}
                  className={`group flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition ${
                    currentSessionId === session.session_id
                      ? "bg-blue-100 text-blue-700"
                      : "text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  <svg
                    className="h-4 w-4 shrink-0 opacity-60"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M2.25 12.75c0 1.636 1.42 3 3.17 3 1.08 0 2.07-.45 2.77-1.17l4.45-4.45c.68-.68 1.96-.68 2.65 0l2.27 2.27c.43.43.68 1 .68 1.63 0 1.636-1.42 3-3.17 3h-2.5c-.66 0-1.27.32-1.65.85l-.02.03c-.7.98-1.89 1.55-3.15 1.55-2.28 0-4.12-1.84-4.12-4.12 0-1.47.77-2.76 1.93-3.49L9.4 3.54"
                    />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <p className="truncate">
                      {session.title || `会话 ${session.session_id.slice(-6)}`}
                    </p>
                    <p className="text-xs text-slate-400">
                      {session.message_count} 条消息
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
                    className="hidden h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-slate-400 transition hover:bg-red-100 hover:text-red-500 group-hover:flex disabled:opacity-50"
                    title="删除"
                  >
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                      />
                    </svg>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 底部 */}
      <div className="border-t border-slate-200 p-4 text-center">
        <p className="text-xs text-slate-400">OilChem Agent v1.3.1</p>
      </div>
    </aside>
  );
}
