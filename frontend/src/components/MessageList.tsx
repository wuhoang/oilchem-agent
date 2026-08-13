/**
 * 消息列表组件。
 *
 * 渲染对话中的所有消息，自动滚动到底部。
 */

import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { Message } from "./Message";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-6">
      {messages.map((msg) => (
        <Message key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

/** 空状态提示。 */
function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-slate-400">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-3xl">
        🧪
      </div>
      <div className="text-center">
        <p className="text-lg font-medium text-slate-600">
          开始与 OilChem Agent 对话
        </p>
        <p className="mt-1 text-sm">
          询问我关于石油化工、文件操作或数据分析的任何问题
        </p>
      </div>
      <SuggestionChips />
    </div>
  );
}

/** 快速建议按钮。 */
function SuggestionChips() {
  const suggestions = [
    "读取 data/input.csv 并分析数据",
    "帮我生成一份实验报告",
    "列出 reports 文件夹里的所有文件",
    "总结一下今天的工作内容",
  ];

  const handleClick = (text: string) => {
    const event = new CustomEvent("oilchem:quick-prompt", { detail: text });
    window.dispatchEvent(event);
  };

  return (
    <div className="mt-2 flex flex-wrap justify-center gap-2 px-6">
      {suggestions.map((text) => (
        <button
          key={text}
          onClick={() => handleClick(text)}
          className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
