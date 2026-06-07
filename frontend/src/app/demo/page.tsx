"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import SessionReportPanel from "@/components/SessionReportPanel";
import {
  FALLBACK_DEMO_ANALYSIS,
  FALLBACK_DEMO_REPORT,
  FALLBACK_DEMO_EVENTS,
  DEMO_SESSION_ID,
} from "@/data/demoData";
import type {
  SessionAnalysisResponse,
  SessionEventsResponse,
  SessionReportResponse,
  TimelineEventItem,
  TranscriptTurn,
} from "@/types/api";

const DEMO_CACHE_KEY = "offergpt-demo-data";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

/** 数据来源 — 用于顶部横幅文案 */
type DataSource = "api" | "cache" | "fallback";

/** 浏览器朗读英文片段（无录音时的降级） */
function speakEnglish(text: string) {
  if (typeof window === "undefined" || !text.trim()) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text.trim());
  utterance.lang = "en-US";
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

/** 尝试从 localStorage 读取缓存 */
function loadFromCache(): DemoData | null {
  try {
    const raw = localStorage.getItem(DEMO_CACHE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as DemoData;
    // 基本校验：必须有 analysis 数据
    if (data.analysis?.sessionId && data.report?.sessionId) {
      return data;
    }
  } catch {
    // parse 失败
  }
  return null;
}

/** 将数据写入 localStorage 缓存 */
function saveToCache(data: DemoData) {
  try {
    localStorage.setItem(DEMO_CACHE_KEY, JSON.stringify(data));
  } catch {
    // localStorage 不可用（无痕浏览、存储满）
  }
}

interface DemoData {
  analysis: SessionAnalysisResponse;
  report: SessionReportResponse;
  events: SessionEventsResponse;
}

export default function DemoPage() {
  const [analysis, setAnalysis] = useState<SessionAnalysisResponse | null>(null);
  const [report, setReport] = useState<SessionReportResponse | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<SessionEventsResponse | null>(null);
  const [reportStatus, setReportStatus] = useState<"loading" | "ready" | "error">("loading");
  const [dataSource, setDataSource] = useState<DataSource>("api");
  const [highlightTurnId, setHighlightTurnId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  /** 播放用户轮次音频（Demo 无录音，使用 TTS 朗读） */
  const playTurnReplay = useCallback(
    (turn: TranscriptTurn | undefined, snippet: string, audioEl: HTMLAudioElement | null) => {
      const url = turn?.role === "user" ? turn.audioUrl : null;
      if (url && audioEl) {
        window.speechSynthesis.cancel();
        audioEl.pause();
        audioEl.src = url;
        void audioEl.play().catch(() => speakEnglish(snippet));
        return;
      }
      speakEnglish(snippet);
    },
    [],
  );

  /** 时间轴事件点击：高亮对应轮次 + 朗读片段 */
  const handleTimelineEventClick = useCallback(
    (event: TimelineEventItem) => {
      if (event.turnId) {
        setHighlightTurnId(event.turnId);
      }
      if (!event.transcriptSnippet) return;
      const userTurn = analysis?.transcriptTurns?.find(
        (t) => t.turnId === event.turnId && t.role === "user",
      );
      if (!audioRef.current && typeof window !== "undefined") {
        audioRef.current = new Audio();
      }
      playTurnReplay(userTurn, event.transcriptSnippet, audioRef.current);
    },
    [analysis?.transcriptTurns, playTurnReplay],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      // 策略 1: 尝试从后端 API 获取最新数据
      try {
        const res = await fetch(`${API_BASE}/api/demo`);
        if (res.ok) {
          const data: DemoData = await res.json();
          if (!cancelled) {
            setAnalysis(data.analysis);
            setReport(data.report);
            setTimelineEvents(data.events);
            setReportStatus("ready");
            setDataSource("api");
            saveToCache(data);
            console.log("[Demo] 从 API 加载数据成功");
          }
          return;
        }
      } catch {
        console.log("[Demo] API 不可用，尝试缓存");
      }

      // 策略 2: 从 localStorage 缓存加载
      const cached = loadFromCache();
      if (cached && !cancelled) {
        setAnalysis(cached.analysis);
        setReport(cached.report);
        setTimelineEvents(cached.events);
        setReportStatus("ready");
        setDataSource("cache");
        console.log("[Demo] 从缓存加载数据成功");
        return;
      }

      // 策略 3: 使用静态兜底数据
      if (!cancelled) {
        setAnalysis(FALLBACK_DEMO_ANALYSIS);
        setReport(FALLBACK_DEMO_REPORT);
        setTimelineEvents(FALLBACK_DEMO_EVENTS);
        setReportStatus("ready");
        setDataSource("fallback");
        console.log("[Demo] 从静态数据加载");
      }
    }

    loadData();

    return () => {
      cancelled = true;
      if (typeof window !== "undefined") {
        window.speechSynthesis.cancel();
        audioRef.current?.pause();
      }
    };
  }, []);

  // ---- 数据来源横幅文案 ----
  const sourceLabel: Record<DataSource, string> = {
    api: "Demo 演示数据 — 实时连接后端",
    cache: "Demo 演示数据 — 离线缓存模式",
    fallback: "Demo 演示数据 — 离线可用（静态数据）",
  };
  const sourceColorClass: Record<DataSource, string> = {
    api: "border-emerald-200 bg-emerald-50 text-emerald-800",
    cache: "border-amber-200 bg-amber-50 text-amber-800",
    fallback: "border-sky-200 bg-sky-50 text-sky-800",
  };

  // ---- Loading 状态 ----
  if (reportStatus === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">正在加载 Demo 数据…</p>
        </div>
      </div>
    );
  }

  // ---- Error 状态 ----
  if (!analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
        <div className="text-center px-4">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-2xl">
            ⚠️
          </div>
          <p className="text-sm font-medium text-zinc-600">Demo 数据加载失败</p>
          <p className="mt-1 text-xs text-zinc-400">
            请确保后端服务已启动并执行了种子数据初始化
          </p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 px-5 py-2 text-sm font-semibold text-white shadow-lg transition hover:scale-105"
          >
            返回首页
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
      {/* 顶部数据来源横幅 */}
      <div className="sticky top-0 z-40 border-b border-zinc-200/60 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${sourceColorClass[dataSource]}`}
          >
            {sourceLabel[dataSource]}
          </div>
          <Link
            href="/"
            className="text-xs font-medium text-indigo-500 transition hover:text-indigo-600"
          >
            ← 返回首页
          </Link>
        </div>
      </div>

      {/* 报告主体 — 复用 SessionReportPanel */}
      <SessionReportPanel
        sessionId={DEMO_SESSION_ID}
        analysis={analysis}
        report={report}
        timelineEvents={timelineEvents}
        reportStatus={reportStatus}
        highlightTurnId={highlightTurnId}
        onTimelineEventClick={handleTimelineEventClick}
      />
    </div>
  );
}
