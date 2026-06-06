"use client";

/** 垂直时间轴事件列表 — 支持点击跳转音频 + 高亮当前播放事件 */

import type { TimelineEventItem } from "@/types/api";

interface TimelineViewerProps {
  events: TimelineEventItem[];
  onEventClick?: (event: TimelineEventItem) => void;
  t: (key: string) => string;
  /** 当前高亮事件 ID（音频正在播放的位置） */
  activeEventId?: string | null;
  /** 是否有录音可回放 */
  hasAudio?: boolean;
}

function formatMs(ms: number): string {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function dotColor(type: string): string {
  if (type === "grammar_error") return "bg-red-500 ring-red-200 dark:ring-red-900";
  if (type === "star_missing") return "bg-amber-500 ring-amber-200 dark:ring-amber-900";
  if (type === "highlight_answer") return "bg-emerald-500 ring-emerald-200 dark:ring-emerald-900";
  return "bg-zinc-400 ring-zinc-200 dark:ring-zinc-700";
}

function borderColor(type: string): string {
  if (type === "grammar_error") return "border-red-200 dark:border-red-900/40";
  if (type === "star_missing") return "border-amber-200 dark:border-amber-900/40";
  if (type === "highlight_answer") return "border-emerald-200 dark:border-emerald-900/40";
  return "border-zinc-200 dark:border-zinc-800";
}

function badgeStyle(type: string): string {
  if (type === "grammar_error") return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
  if (type === "star_missing") return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
  return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
}

export default function TimelineViewer({ events, onEventClick, t, activeEventId, hasAudio }: TimelineViewerProps) {
  if (events.length === 0) {
    return <p className="text-sm text-zinc-400">{t("report.timelineEmpty")}</p>;
  }

  return (
    <div className="relative ml-2">
      <div className="absolute left-[11px] top-3 bottom-3 w-0.5 bg-zinc-200 dark:bg-zinc-700" />
      <div className="space-y-4">
        {events.map((event) => {
          const isActive = activeEventId === event.eventId;
          return (
            <div key={event.eventId} className="relative flex gap-4 pl-7">
              {/* 时间点圆点 — 选中时放大 + 脉冲动画 */}
              <div
                className={`absolute left-0 mt-1.5 rounded-full border-2 border-white dark:border-zinc-900 ring-2 transition-all duration-300 ${
                  isActive
                    ? "h-[26px] w-[26px] -left-[2px] mt-[11px] animate-pulse"
                    : "h-[22px] w-[22px] mt-1.5"
                } ${dotColor(event.eventType)}`}
              />
              <button
                type="button"
                className={`flex-1 rounded-xl border p-4 text-left transition-all duration-300 ${
                  isActive
                    ? "bg-indigo-50 border-indigo-300 shadow-md dark:bg-indigo-950/30 dark:border-indigo-700"
                    : `bg-white hover:bg-zinc-50 dark:bg-zinc-900 dark:hover:bg-zinc-800/70 ${borderColor(event.eventType)}`
                }`}
                onClick={() => onEventClick?.(event)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${badgeStyle(event.eventType)}`}>
                    {t(`report.event.${event.eventType}`)}
                  </span>
                  <span className="text-[11px] text-zinc-400">
                    {formatMs(event.startMs)} – {formatMs(event.endMs)}
                  </span>
                  {isActive && (
                    <span className="ml-auto flex items-center gap-1 text-[11px] text-indigo-500 font-medium">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                      {t("report.playing")}
                    </span>
                  )}
                </div>
                <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{event.title}</h4>
                {event.description && <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{event.description}</p>}
                {event.transcriptSnippet && (
                  <p className="mt-2 rounded-md bg-zinc-50 px-3 py-2 text-xs italic text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                    &ldquo;{event.transcriptSnippet}&rdquo;
                  </p>
                )}
                {event.aiResponse && (
                  <p className="mt-2 rounded-md bg-indigo-50/50 px-3 py-2 text-xs text-indigo-700 dark:bg-indigo-950/20 dark:text-indigo-300">
                    <span className="font-semibold">{t("report.aiResponse")}</span>
                    {event.aiResponse.length > 200
                      ? event.aiResponse.slice(0, 200) + "…"
                      : event.aiResponse}
                  </p>
                )}
                {event.suggestion && <p className="mt-2 text-xs text-indigo-600 dark:text-indigo-400">💡 {event.suggestion}</p>}
                <p className="mt-2 text-[10px] text-zinc-400">
                  {hasAudio ? t("report.clickToPlay") : t("report.jumpToTranscript") + " →"}
                </p>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
