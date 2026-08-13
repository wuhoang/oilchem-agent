/**
 * 单条消息组件。
 *
 * 根据消息角色渲染不同样式，支持流式打字机效果、
 * 思考过程展示和工具调用信息。支持 Markdown 渲染。
 */

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, ToolCallInfo } from "../types";

interface MessageProps {
  message: ChatMessage;
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === "user";
  const [showThinking, setShowThinking] = useState(true);

  return (
    <div
      className={`flex gap-3 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      {/* Avatar */}
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ${
          isUser
            ? "bg-blue-600"
            : "bg-gradient-to-br from-emerald-500 to-teal-600"
        }`}
      >
        {isUser ? "我" : "AI"}
      </div>

      {/* Message content */}
      <div
        className={`group flex max-w-[80%] flex-col gap-1 ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        {/* Thinking / Tool calls section */}
        {!isUser && (message.thinking || message.toolCalls?.length) ? (
          <div
            className="w-full max-w-xl rounded-xl border border-slate-200 bg-slate-50 text-xs"
          >
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-500 transition hover:text-slate-700"
            >
              <svg
                className={`h-3.5 w-3.5 transition-transform ${showThinking ? "rotate-90" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
              <span>思考过程</span>
              {!showThinking && (
                <span className="ml-auto text-slate-400">
                  {message.toolCalls?.length || 0} 步
                </span>
              )}
            </button>
            {showThinking && (
              <div className="border-t border-slate-200 px-3 py-2 space-y-2">
                {message.toolCalls?.map((tc, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 rounded-md bg-white p-2"
                  >
                    <StatusIcon status={tc.status} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500 text-xs">工具调用 {tc.call_index}</span>
                        {tc.tool_name && (
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-600">
                            {tc.tool_name}
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-slate-700 text-xs">{tc.description}</p>
                      {tc.result && (
                        <p className="mt-1 text-slate-500 text-xs truncate">
                          {tc.result}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
                {message.thinking && !message.toolCalls?.length && (
                  <p className="text-slate-600 text-xs leading-relaxed whitespace-pre-wrap">
                    {message.thinking}
                  </p>
                )}
              </div>
            )}
          </div>
        ) : null}

        {/* Main message bubble */}
        <div
          className={`markdown-body rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
            isUser
              ? "bg-blue-600 text-white"
              : "border border-slate-200 bg-white text-slate-800"
          } ${message.streaming ? "animate-pulse" : ""}`}
        >
          {message.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ inline, className, children, ...props }: any) {
                  return !inline ? (
                    <pre className="mt-2 mb-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                  ) : (
                    <code
                      className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs text-slate-700"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                },
                table({ children }: any) {
                  return (
                    <div className="my-2 overflow-x-auto">
                      <table className="border-collapse text-xs">{children}</table>
                    </div>
                  );
                },
                th({ children }: any) {
                  return (
                    <th className="border border-slate-300 bg-slate-100 px-2 py-1 text-left font-semibold">
                      {children}
                    </th>
                  );
                },
                td({ children }: any) {
                  return (
                    <td className="border border-slate-300 px-2 py-1">{children}</td>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : (
            <span className="text-slate-400">
              <TypingDots />
            </span>
          )}
        </div>

        {/* Charts */}
        {!isUser && message.charts && message.charts.length > 0 && (
          <div className="flex flex-col gap-2">
            {message.charts.map((chart, idx) => (
              <div
                key={idx}
                className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
              >
                <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2">
                  <span className="text-xs font-medium text-slate-600">
                    📊 {chart.chart_type.toUpperCase()} 图表
                  </span>
                  <span className="text-xs text-slate-400">
                    {chart.width}×{chart.height}
                  </span>
                </div>
                <div className="flex justify-center bg-white p-2">
                  <img
                    src={`data:${chart.image_mime};base64,${chart.image_base64}`}
                    alt={`${chart.chart_type} chart`}
                    className="max-w-full rounded"
                    style={{ maxHeight: "400px" }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <span className="px-1 text-xs text-slate-400">
          {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: ToolCallInfo["status"] }) {
  const icons = {
    pending: (
      <svg className="h-3.5 w-3.5 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="10" />
      </svg>
    ),
    running: (
      <span className="flex h-3.5 w-3.5 items-center justify-center">
        <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-blue-300 border-t-blue-500" />
      </span>
    ),
    success: (
      <svg className="h-3.5 w-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
    ),
    error: (
      <svg className="h-3.5 w-3.5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
    ),
  };
  return <span className="mt-0.5">{icons[status]}</span>;
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
    </span>
  );
}
