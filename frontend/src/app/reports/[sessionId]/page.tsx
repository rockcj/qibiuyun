"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import SessionReportPanel from "@/components/SessionReportPanel";
import { getSessionAnalysis, getSessionEvents, getSessionReport } from "@/lib/api";
import type {
  SessionAnalysisResponse,
  SessionEventsResponse,
  SessionReportResponse,
  TimelineEventItem,
  TranscriptTurn,
} from "@/types/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

/** 将相对回放路径转为完整 URL */
function resolveAudioUrl(path?: string): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

/** 浏览器朗读英文片段（无录音时的降级） */
function speakEnglish(text: string) {
  if (typeof window === "undefined" || !text.trim()) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text.trim());
  utterance.lang = "en-US";
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

/** 播放用户轮次真实录音，无录音则 TTS 朗读片段 */
function playTurnReplay(turn: TranscriptTurn | undefined, snippet: string, audioEl: HTMLAudioElement | null) {
  const url = turn?.role === "user" ? resolveAudioUrl(turn.audioUrl) : null;
  if (url && audioEl) {
    window.speechSynthesis.cancel();
    audioEl.pause();
    audioEl.src = url;
    void audioEl.play().catch(() => speakEnglish(snippet));
    return;
  }
  speakEnglish(snippet);
}

export default function ReportPage() {
  const { t } = useLocale();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [analysis, setAnalysis] = useState<SessionAnalysisResponse | null>(null);
  const [report, setReport] = useState<SessionReportResponse | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<SessionEventsResponse | null>(null);
  const [reportStatus, setReportStatus] = useState<"loading" | "generating" | "ready" | "error">("loading");
  const [highlightTurnId, setHighlightTurnId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handleTimelineEventClick = useCallback(
    (event: TimelineEventItem) => {
      if (event.turnId) {
        setHighlightTurnId(event.turnId);
      }
      if (!event.transcriptSnippet) return;
      const userTurn = analysis?.transcriptTurns?.find(
        (t) => t.turnId === event.turnId && t.role === "user"
      );
      if (!audioRef.current && typeof window !== "undefined") {
        audioRef.current = new Audio();
      }
      playTurnReplay(userTurn, event.transcriptSnippet, audioRef.current);
    },
    [analysis?.transcriptTurns]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      try {
        const analysisData = await getSessionAnalysis(sessionId);
        if (!cancelled) setAnalysis(analysisData);
      } catch {
        if (!cancelled) {
          setAnalysis({
            sessionId,
            pronunciation: [],
            corrections: [],
            fillerCounts: {},
            transcriptTurns: [],
          });
        }
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
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
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
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      if (typeof window !== "undefined") {
        window.speechSynthesis.cancel();
        audioRef.current?.pause();
      }
    };
  }, [sessionId]);

  if (reportStatus === "loading" && !analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">{t("report.loading")}</p>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-2xl">⚠️</div>
          <p className="text-sm font-medium text-zinc-600">{t("report.error")}</p>
          <Link href="/" className="mt-4 inline-block text-sm font-semibold text-indigo-500 hover:text-indigo-600">
            返回首页
          </Link>
        </div>
      </div>
    );
  }

  return (
    <SessionReportPanel
      sessionId={sessionId}
      analysis={analysis}
      report={report}
      timelineEvents={timelineEvents}
      reportStatus={reportStatus}
      highlightTurnId={highlightTurnId}
      onTimelineEventClick={handleTimelineEventClick}
    />
  );
}
