"use client";

/** 会话内 transient 提示条样式 */
export type SessionNoticeKind = "info" | "warning" | "success" | "error";

interface SessionNoticeBannerProps {
  kind: SessionNoticeKind;
  message: string;
  /** 可选标题（如「语法纠正已关闭」） */
  title?: string;
  onDismiss?: () => void;
}

const kindStyles: Record<SessionNoticeKind, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950/80 dark:text-sky-100",
  warning:
    "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/80 dark:text-amber-100",
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-100",
  error: "border-red-200 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/80 dark:text-red-100",
};

/**
 * 会话页顶部/底部非模态提示条，用于 ASR 失败、纠正开关、模式切换等反馈。
 */
export default function SessionNoticeBanner({
  kind,
  message,
  title,
  onDismiss,
}: SessionNoticeBannerProps) {
  return (
    <div
      role="status"
      className={`flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm shadow-sm ${kindStyles[kind]}`}
    >
      <div className="min-w-0 flex-1">
        {title && <p className="mb-0.5 text-xs font-semibold opacity-90">{title}</p>}
        <p className="leading-relaxed">{message}</p>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md px-1.5 py-0.5 text-xs opacity-60 transition-opacity hover:opacity-100"
          aria-label="Dismiss"
        >
          ✕
        </button>
      )}
    </div>
  );
}
