"use client";

/** 垂直时间轴事件列表 — 纯 Tailwind 实现 */

import type { TimelineEventItem } from "@/types/api";

interface TimelineViewerProps {
  events: TimelineEventItem[];
  onEventClick?: (event: TimelineEventItem) => void;
  /** i18n 翻译函数 */
  t: (key: string) => string;
}

function formatMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

function eventColor(eventType: string): string {
  switch (eventType) {
    case "grammar_error":
      return "bg-red-500 ring-red-200 dark:ring-red-900";
    case "star_missing":
      return "bg-amber-500 ring-amber-200 dark:ring-amber-900";
    case "highlight_answer":
      return "bg-emerald-500 ring-emerald-200 dark:ring-emerald-900";
    default:
      return "bg-zinc-400 ring-zinc-200 dark:ring-zinc-700";
  }
}

function eventCardBorder(eventType: string): string {
  switch (eventType) {
    case "grammar_error":
      return "border-red-200 dark:border-red-900/40";
    case "star_missing":
      return "border-amber-200 dark:border-amber-900/40";
    case "highlight_answer":
      return "border-emerald-200 dark:border-emerald-900/40";
    default:
      return "border-zinc-200 dark:border-zinc-800";
  }
}

function eventTypeLabel(eventType: string, t: (key: string) => string): string {
  const key = `report.event.${eventType}`;
  const translated = t(key);
  return translated === key ? eventType : translated;
}

export default function TimelineViewer({
  events,
  onEventClick,
  t,
}: TimelineViewerProps) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-zinc-400">{t("report.timelineEmpty")}</p>
    );
  }

  return (
    <div className="relative ml-2">
      {/* 左侧时间轴线 */}
      <div className="absolute left-[11px] top-3 bottom-3 w-0.5 bg-zinc-200 dark:bg-zinc-700" />

      <div className="space-y-4">
        {events.map((event) => (
          <div key={event.eventId} className="relative flex gap-4 pl-7">
            {/* 时间轴圆点 */}
            <div
              className={`absolute left-0 mt-1.5 h-[22px] w-[22px] rounded-full border-2 border-white dark:border-zinc-900 ${eventColor(event.eventType)} ring-2`}
            />

            {/* 事件卡片 */}
            <button
              type="button"
              className={`flex-1 rounded-xl border bg-white p-4 text-left transition-colors hover:bg-zinc-50 dark:bg-zinc-900 dark:hover:bg-zinc-800/70 ${eventCardBorder(event.eventType)}`}
              onClick={() => onEventClick?.(event)}
              title={t("report.jumpToTranscript")}
            >
              {/* 事件类型 + 严重程度 */}
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    event.eventType === "grammar_error"
                      ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                      : event.eventType === "star_missing"
                        ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                        : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                  }`}
                >
                  {eventTypeLabel(event.eventType, t)}
                </span>
                <span className="text-[11px] text-zinc-400">
                  {formatMs(event.startMs)} – {formatMs(event.endMs)}
                </span>
              </div>

              {/* 标题 */}
              <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                {event.title}
              </h4>

              {/* 描述 */}
              {event.description && (
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {event.description}
                </p>
              )}

              {/* 转录片段 */}
              {event.transcriptSnippet && (
                <p className="mt-2 rounded-md bg-zinc-50 px-3 py-2 text-xs italic text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                  &ldquo;{event.transcriptSnippet}&rdquo;
                </p>
              )}

              {/* 建议 */}
              {event.suggestion && (
                <p className="mt-2 text-xs text-indigo-600 dark:text-indigo-400">
                  💡 {event.suggestion}
                </p>
              )}

              {/* 点击提示 */}
              <p className="mt-2 text-[10px] text-zinc-400">
                {t("report.jumpToTranscript")} →
              </p>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
