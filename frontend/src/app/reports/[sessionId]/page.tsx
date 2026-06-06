"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import SessionReportPanel from "@/components/SessionReportPanel";
import { getSessionAnalysis, getSessionEvents, getSessionReport, getInterviewDetail } from "@/lib/api";
import type {
  SessionAnalysisResponse,
  SessionEventsResponse,
  SessionReportResponse,
  TimelineEventItem,
} from "@/types/api";

export default function ReportPage() {
  const { t } = useLocale();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [analysis, setAnalysis] = useState<SessionAnalysisResponse | null>(null);
  const [report, setReport] = useState<SessionReportResponse | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<SessionEventsResponse | null>(null);
  const [reportStatus, setReportStatus] = useState<"loading" | "generating" | "ready" | "error">("loading");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  /** 点击时间轴事件 → 跳转音频并播放 */
  const handleTimelineEventClick = useCallback((event: TimelineEventItem) => {
    const audio = audioRef.current;
    if (!audio || !audio.src) {
      console.log("[Report] 无录音可播放");
      return;
    }
    const seekTime = event.startMs / 1000;
    audio.currentTime = seekTime;
    audio.play().catch((err) => console.warn("[Report] 音频播放失败:", err));
    setActiveEventId(event.eventId);
    console.log(`[Report] 跳转到 ${seekTime.toFixed(1)}s: ${event.title}`);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      // 加载会话详情获取 audioUrl
      try {
        const detail = await getInterviewDetail(sessionId);
        if (!cancelled && detail.audioUrl) {
          setAudioUrl(detail.audioUrl);
        }
      } catch {
        console.log("[Report] 获取 audioUrl 失败");
      }

      try {
        const analysisData = await getSessionAnalysis(sessionId);
        if (!cancelled) setAnalysis(analysisData);
      } catch {
        if (!cancelled) setAnalysis({ sessionId, pronunciation: [], corrections: [], fillerCounts: {} });
      }

      try {
        const eventsData = await getSessionEvents(sessionId);
        if (!cancelled) setTimelineEvents(eventsData);
      } catch {
        if (!cancelled) setTimelineEvents({ sessionId, events: [] });
      }

      if (!cancelled) await checkReport();
    }

    async function checkReport() {
      try {
        const reportData = await getSessionReport(sessionId);
        if (cancelled) return;
        const status = reportData.reportStatus ?? "ready";
        setReportStatus(status);
        if (status === "ready") {
          setReport(reportData);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        } else if (status === "generating") {
          setReport(reportData);
          if (!pollRef.current) pollRef.current = setInterval(checkReport, 3000);
        }
      } catch {
        if (!cancelled) setReportStatus("error");
      }
    }

    if (sessionId) loadInitial();

    return () => {
      cancelled = true;
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [sessionId]);

  if (reportStatus === "loading" && !analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">{t("report.loading")}</p>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-2xl dark:bg-red-900/30">⚠️</div>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("report.error")}</p>
          <Link href="/" className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-500">{t("report.backHomeFallback")}</Link>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* 隐藏的音频播放器 */}
      <audio ref={audioRef} src={audioUrl || undefined} preload="auto" />

      <SessionReportPanel
        sessionId={sessionId}
        analysis={analysis}
        report={report}
        timelineEvents={timelineEvents}
        reportStatus={reportStatus}
        onTimelineEventClick={handleTimelineEventClick}
        activeEventId={activeEventId}
        hasAudio={!!audioUrl}
      />
    </>
  );
}
