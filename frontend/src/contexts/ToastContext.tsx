"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

/** Toast 通知类型 — 与 SessionNoticeBanner 的 kind 保持一致 */
export type ToastKind = "info" | "success" | "warning" | "error";

/** 单条 Toast */
export interface ToastItem {
  id: string;
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  toasts: ToastItem[];
  /** 弹出 Toast，默认 5 秒后自动消失 */
  showToast: (message: string, kind?: ToastKind) => void;
  /** 手动关闭指定 Toast */
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue>({
  toasts: [],
  showToast: () => {},
  dismissToast: () => {},
});

/** 全局 Toast 计数器 */
let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, kind: ToastKind = "info") => {
      const id = `toast_${++toastCounter}_${Date.now()}`;
      const newToast: ToastItem = { id, message, kind };

      setToasts((prev) => {
        // 最多同时显示 3 条
        const next = [...prev, newToast];
        if (next.length > 3) {
          return next.slice(-3);
        }
        return next;
      });

      // 自动消失（5 秒）
      if (typeof window !== "undefined") {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 5000);
      }
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ toasts, showToast, dismissToast }}>
      {children}
      {/* Toast 容器 — 固定底部居中 */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

// ---------------------------------------------------------------------------
// Toast 容器组件
// ---------------------------------------------------------------------------

const kindStyles: Record<ToastKind, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  error: "border-red-200 bg-red-50 text-red-900",
};

function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-6 left-1/2 z-[100] flex -translate-x-1/2 flex-col items-center gap-2"
      aria-live="polite"
      aria-label="通知"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg animate-slide-up ${kindStyles[toast.kind]}`}
          style={{
            maxWidth: "calc(100vw - 2rem)",
            animation: "slideUp 0.3s ease-out",
          }}
        >
          <span className="min-w-0 flex-1 leading-relaxed">{toast.message}</span>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            className="shrink-0 rounded-md px-1.5 py-0.5 text-xs opacity-60 transition-opacity hover:opacity-100"
            aria-label="关闭通知"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
