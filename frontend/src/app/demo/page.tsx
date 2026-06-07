"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import SessionReportPanel from "@/components/SessionReportPanel";
import {
  DEMO_SESSION_ID,
  getFallbackDemoData,
} from "@/data/demoData";
import type {
  SessionAnalysisResponse,
  SessionEventsResponse,
  SessionReportResponse,
  TimelineEventItem,
  TranscriptTurn,
} from "@/types/api";

const DEMO_CACHE_KEY_PREFIX = "offergpt-demo-data";

/** 从 URL 中读取当前场景（query param "scene"），默认 interview */
function getSceneFromUrl(): string {
  if (typeof window === "undefined") return "interview";
  const params = new URLSearchParams(window.location.search);
  return params.get("scene") || "interview";
}

/** 更新 URL 的 scene 参数（不刷新页面） */
function updateSceneInUrl(scene: string) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set("scene", scene);
  window.history.replaceState({}, "", url.toString());
}

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
function loadFromCache(scene: string): DemoData | null {
  try {
    const raw = localStorage.getItem(`${DEMO_CACHE_KEY_PREFIX}-${scene}`);
    if (!raw) return null;
    const data = JSON.parse(raw) as DemoData;
    if (data.analysis?.sessionId && data.report?.sessionId) {
      return data;
    }
  } catch {
    // parse 失败
  }
  return null;
}

/** 将数据写入 localStorage 缓存 */
function saveToCache(scene: string, data: DemoData) {
  try {
    localStorage.setItem(`${DEMO_CACHE_KEY_PREFIX}-${scene}`, JSON.stringify(data));
  } catch {
    // localStorage 不可用
  }
}

interface DemoData {
  analysis: SessionAnalysisResponse;
  report: SessionReportResponse;
  events: SessionEventsResponse;
}

const SCENE_OPTIONS = [
  { scene: "interview", label: "求职面试", icon: "💼" },
  { scene: "restaurant", label: "餐厅点餐", icon: "🍽️" },
  { scene: "meeting", label: "商务会议", icon: "📊" },
];

export default function DemoPage() {
  const [scene, setScene] = useState<string>(getSceneFromUrl);
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
      setReportStatus("loading");

      // 策略 1: 尝试从后端 API 获取最新数据
      try {
        const res = await fetch(`${API_BASE}/api/demo?scene=${scene}`);
        if (res.ok) {
          const data: DemoData = await res.json();
          if (!cancelled) {
            setAnalysis(data.analysis);
            setReport(data.report);
            setTimelineEvents(data.events);
            setReportStatus("ready");
            setDataSource("api");
            saveToCache(scene, data);
            console.log(`[Demo] 从 API 加载 ${scene} 数据成功`);
          }
          return;
        }
      } catch {
        console.log(`[Demo] API 不可用（${scene}），尝试缓存`);
      }

      // 策略 2: 从 localStorage 缓存加载
      const cached = loadFromCache(scene);
      if (cached && !cancelled) {
        setAnalysis(cached.analysis);
        setReport(cached.report);
        setTimelineEvents(cached.events);
        setReportStatus("ready");
        setDataSource("cache");
        console.log(`[Demo] 从缓存加载 ${scene} 数据成功`);
        return;
      }

      // 策略 3: 使用静态兜底数据
      if (!cancelled) {
        const fallback = getFallbackDemoData(scene);
        setAnalysis(fallback.analysis);
        setReport(fallback.report);
        setTimelineEvents(fallback.events);
        setReportStatus("ready");
        setDataSource("fallback");
        console.log(`[Demo] 从静态数据加载 ${scene}`);
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
  }, [scene]);

  /** 切换场景 */
  const handleSceneChange = (newScene: string) => {
    setScene(newScene);
    updateSceneInUrl(newScene);
  };

  /** 获取当前场景的 sessionId */
  const currentSessionId = (() => {
    const fallback = getFallbackDemoData(scene);
    return fallback.analysis?.sessionId || DEMO_SESSION_ID;
  })();

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
      {/* 顶部数据来源横幅 + 场景选择器 */}
      <div className="sticky top-0 z-40 border-b border-zinc-200/60 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <div
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${sourceColorClass[dataSource]}`}
            >
              {sourceLabel[dataSource]}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 场景切换按钮组 */}
            <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5">
              {SCENE_OPTIONS.map((opt) => (
                <button
                  key={opt.scene}
                  type="button"
                  onClick={() => handleSceneChange(opt.scene)}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${
                    scene === opt.scene
                      ? "bg-white text-zinc-800 shadow-sm"
                      : "text-zinc-400 hover:text-zinc-600"
                  }`}
                >
                  <span className="mr-1">{opt.icon}</span>
                  {opt.label}
                </button>
              ))}
            </div>
            <Link
              href="/"
              className="text-xs font-medium text-indigo-500 transition hover:text-indigo-600"
            >
              ← 返回首页
            </Link>
          </div>
        </div>
      </div>

      {/* 报告主体 — 复用 SessionReportPanel */}
      <SessionReportPanel
        sessionId={currentSessionId}
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
