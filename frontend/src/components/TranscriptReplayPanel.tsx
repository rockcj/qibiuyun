"use client";

import { useCallback, useEffect, useRef } from "react";
import type { TranscriptTurn } from "@/types/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

interface TranscriptReplayPanelProps {
  turns: TranscriptTurn[];
  highlightTurnId?: string | null;
  fullAudioUrl?: string | null;
  onPlayTurn?: (turn: TranscriptTurn) => void;
  t: (key: string) => string;
}

/** 将相对回放路径转为完整 URL */
function resolveAudioUrl(path?: string): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

/** 格式化毫秒为 m:ss */
function formatMs(ms: number): string {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** 对话 transcript 回放列表（优先播放真实录音 WAV） */
export default function TranscriptReplayPanel({
  turns,
  highlightTurnId,
  fullAudioUrl,
  onPlayTurn,
  t,
}: TranscriptReplayPanelProps) {
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // 高亮轮次时滚动到可见区域
  useEffect(() => {
    if (!highlightTurnId) return;
    const el = itemRefs.current[highlightTurnId];
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightTurnId]);

  /** 播放指定 URL 的 WAV；无 URL 时降级为浏览器 TTS */
  const playAudioOrSpeak = useCallback((url: string | null, fallbackText: string) => {
    if (url) {
      if (!audioRef.current) {
        audioRef.current = new Audio();
      }
      const audio = audioRef.current;
      audio.pause();
      audio.src = url;
      void audio.play().catch(() => {
        // 自动播放被拦截时降级 TTS
        if (typeof window !== "undefined" && fallbackText.trim()) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(fallbackText.trim());
          utterance.lang = "en-US";
          utterance.rate = 0.95;
          window.speechSynthesis.speak(utterance);
        }
      });
      return;
    }
    if (typeof window !== "undefined" && fallbackText.trim()) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(fallbackText.trim());
      utterance.lang = "en-US";
      utterance.rate = 0.95;
      window.speechSynthesis.speak(utterance);
    }
  }, []);

  const handlePlay = useCallback(
    (turn: TranscriptTurn) => {
      const url = turn.role === "user" ? resolveAudioUrl(turn.audioUrl) : null;
      playAudioOrSpeak(url, turn.text);
      onPlayTurn?.(turn);
    },
    [onPlayTurn, playAudioOrSpeak]
  );

  const handlePlayFull = useCallback(() => {
    playAudioOrSpeak(resolveAudioUrl(fullAudioUrl ?? undefined), "");
  }, [fullAudioUrl, playAudioOrSpeak]);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (typeof window !== "undefined") {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  if (turns.length === 0) {
    return <p className="text-sm text-zinc-400">{t("report.transcriptEmpty")}</p>;
  }

  const resolvedFullUrl = resolveAudioUrl(fullAudioUrl ?? undefined);

  return (
    <div className="space-y-3">
      {resolvedFullUrl && (
        <div className="flex items-center justify-between rounded-xl border border-indigo-200 bg-indigo-50/60 px-4 py-3 dark:border-indigo-800 dark:bg-indigo-950/30">
          <span className="text-sm font-medium text-indigo-800 dark:text-indigo-200">
            {t("report.fullSessionAudio")}
          </span>
          <button
            type="button"
            onClick={handlePlayFull}
            className="rounded-lg border border-indigo-300 px-3 py-1.5 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100 dark:border-indigo-700 dark:text-indigo-300 dark:hover:bg-indigo-900/50"
          >
            ▶ {t("report.playFullSession")}
          </button>
        </div>
      )}

      {turns.map((turn, idx) => {
        const isUser = turn.role === "user";
        const highlighted = highlightTurnId === turn.turnId;
        const refKey = `${turn.turnId}-${turn.role}-${idx}`;
        const hasRecording = isUser && Boolean(turn.audioUrl);

        return (
          <div
            key={refKey}
            ref={(el) => {
              itemRefs.current[turn.turnId] = el;
            }}
            className={`rounded-xl border p-4 transition-colors ${
              highlighted
                ? "border-indigo-400 bg-indigo-50 dark:border-indigo-600 dark:bg-indigo-950/40"
                : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      isUser
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                        : "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
                    }`}
                  >
                    {isUser ? t("report.roleUser") : t("report.roleAssistant")}
                  </span>
                  <span className="font-mono text-[11px] text-zinc-400">{turn.turnId}</span>
                  <span className="text-[11px] text-zinc-400">
                    {formatMs(turn.startMs)} – {formatMs(turn.endMs)}
                  </span>
                  {hasRecording && (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400">WAV</span>
                  )}
                </div>
                <p className="text-sm text-zinc-700 dark:text-zinc-300">&ldquo;{turn.text}&rdquo;</p>
              </div>
              <button
                type="button"
                onClick={() => handlePlay(turn)}
                className="flex-shrink-0 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-indigo-600 transition hover:bg-indigo-50 dark:border-zinc-700 dark:text-indigo-400 dark:hover:bg-indigo-950/50"
                title={hasRecording ? t("report.playRecording") : t("report.playTurn")}
              >
                ▶ {hasRecording ? t("report.playRecording") : t("report.playTurn")}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
