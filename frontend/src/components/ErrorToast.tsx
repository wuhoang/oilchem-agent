/**
 * 全局错误提示条。
 *
 * 通过 CustomEvent 机制接收错误消息，在页面顶部展示红色提示，
 * 自动消失。任何组件通过 notifyError() 即可触发。
 */

import { useEffect, useState } from "react";

export const ERROR_EVENT = "oilchem:error";

/** 派发一条全局错误提示。 */
export function notifyError(message: string): void {
  window.dispatchEvent(new CustomEvent(ERROR_EVENT, { detail: message }));
}

interface ToastItem {
  id: number;
  message: string;
}

const AUTO_DISMISS_MS = 6000;

export function ErrorToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      const message = customEvent.detail || "未知错误";
      const id = Date.now() + Math.random();

      setToasts((prev) => [...prev, { id, message }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, AUTO_DISMISS_MS);
    };

    window.addEventListener(ERROR_EVENT, handler);
    return () => window.removeEventListener(ERROR_EVENT, handler);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed left-1/2 top-4 z-50 flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="alert"
          className="pointer-events-auto flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-lg animate-slide-down"
        >
          <svg
            className="mt-0.5 h-4 w-4 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <span className="min-w-0 break-words">{t.message}</span>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="ml-auto shrink-0 text-red-400 transition hover:text-red-600"
            aria-label="关闭"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
