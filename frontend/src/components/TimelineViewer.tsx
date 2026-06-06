"use client";

/** 垂直时间轴事件列表 */

import type { TimelineEventItem } from "@/types/api";

interface TimelineViewerProps {
  events: TimelineEventItem[];
  onEventClick?: (event: TimelineEventItem) => void;
  t: (key: string) => string;
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

export default function TimelineViewer({ events, onEventClick, t }: TimelineViewerProps) {
  if (events.length === 0) {
    return <p className="text-sm text-zinc-400">{t("report.timelineEmpty")}</p>;
  }

  return (
    <div className="relative ml-2">
      <div className="absolute left-[11px] top-3 bottom-3 w-0.5 bg-zinc-200 dark:bg-zinc-700" />
      <div className="space-y-4">
        {events.map((event) => (
          <div key={event.eventId} className="relative flex gap-4 pl-7">
            <div className={`absolute left-0 mt-1.5 h-[22px] w-[22px] rounded-full border-2 border-white dark:border-zinc-900 ${dotColor(event.eventType)} ring-2`} />
            <button type="button"
              className={`flex-1 rounded-xl border bg-white p-4 text-left transition-colors hover:bg-zinc-50 dark:bg-zinc-900 dark:hover:bg-zinc-800/70 ${borderColor(event.eventType)}`}
              onClick={() => onEventClick?.(event)}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${badgeStyle(event.eventType)}`}>
                  {t(`report.event.${event.eventType}`)}
                </span>
                <span className="text-[11px] text-zinc-400">{formatMs(event.startMs)} – {formatMs(event.endMs)}</span>
              </div>
              <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{event.title}</h4>
              {event.description && <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{event.description}</p>}
              {event.transcriptSnippet && (
                <p className="mt-2 rounded-md bg-zinc-50 px-3 py-2 text-xs italic text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                  &ldquo;{event.transcriptSnippet}&rdquo;
                </p>
              )}
              {event.suggestion && <p className="mt-2 text-xs text-indigo-600 dark:text-indigo-400">💡 {event.suggestion}</p>}
              <p className="mt-2 text-[10px] text-indigo-500 dark:text-indigo-400">{t("report.jumpToTranscript")} →</p>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
