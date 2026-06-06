"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";
import { useMicrophone } from "@/hooks/useMicrophone";
import { useWebSocket, type ConnectionStatus } from "@/hooks/useWebSocket";
import type { CreateSessionResponse, TurnRecord, WsServerMessage } from "@/types/api";
import CorrectionToast from "@/components/CorrectionToast";
import SessionNoticeBanner, { type SessionNoticeKind } from "@/components/SessionNoticeBanner";
import { finishSession } from "@/lib/api";

// 生成全局唯一 ID，避免 React 用 index 做 key 导致聊天框抖动
// 兼容不支持 crypto.randomUUID() 的旧浏览器
const nextId = (): string => {
  try {
    return crypto.randomUUID();
  } catch {
    // fallback: timestamp + random hex
    return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  }
};

interface VoiceSessionPanelProps {
  session: CreateSessionResponse;
}

function StatusBadge({ status }: { status: ConnectionStatus }) {
  const colors: Record<ConnectionStatus, string> = {
    mic_ready: "bg-emerald-500",
    connected: "bg-emerald-400",
    connecting: "bg-amber-500 animate-pulse",
    disconnected: "bg-zinc-400",
    error: "bg-red-500",
  };
  const labels: Record<ConnectionStatus, string> = {
    mic_ready: "就绪",
    connected: "已连接",
    connecting: "连接中…",
    disconnected: "未连接",
    error: "错误",
  };
  return (
    <span className="flex items-center gap-1.5 text-xs text-zinc-500">
      <span className={`h-2 w-2 rounded-full ${colors[status]}`} />
      {labels[status]}
    </span>
  );
}

export default function VoiceSessionPanel({ session }: VoiceSessionPanelProps) {
  const { t } = useLocale();
  const router = useRouter();

  // ---- 输入模式 ----
  const [inputMode, setInputMode] = useState<"text" | "voice">("voice");
  const [textInput, setTextInput] = useState("");
  // 语音模式就绪追踪：只有 WS 已连 + 麦克风 active 才为 true
  const [voiceReady, setVoiceReady] = useState(false);
  // 麦克风初始化开始时间（用于 5 秒超时降级）
  const micPrepStartRef = useRef(0);

  // ---- 对话状态 ----
  const [turns, setTurns] = useState<TurnRecord[]>([]);
  const [streamingAiText, setStreamingAiText] = useState("");
  const [streamingTurnId, setStreamingTurnId] = useState<string | null>(null); // 正在流式输出的 turn
  const [correction, setCorrection] = useState<
    { original: string; corrected: string } | undefined
  >();
  // 轻纠正 Toast 提示（非模态，自动消失）
  const [toastTip, setToastTip] = useState<
    { original: string; corrected: string; spokenTip: string } | null
  >(null);
  // 语气词累计计数
  const [fillerCounts, setFillerCounts] = useState<Record<string, number>>({});
  // 实时轻纠正开关（默认开启，由服务端 correction.state 同步）
  const [correctionEnabled, setCorrectionEnabled] = useState(true);
  const correctionEnabledRef = useRef(true);
  const [isEnding, setIsEnding] = useState(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const [streamingUserText, setStreamingUserText] = useState("");
  // 会话内 transient 提示（ASR 失败、纠正开关等）
  const [sessionNotice, setSessionNotice] = useState<{
    kind: SessionNoticeKind;
    title?: string;
    message: string;
  } | null>(null);
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const correctionInitRef = useRef(false);

  // ---- Refs ----
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingQueueRef = useRef(false);
  /** 浏览器朗读队列（服务端 TTS 关闭时使用） */
  const browserSpeechQueueRef = useRef<string[]>([]);
  const isBrowserSpeakingRef = useRef(false);
  const ttsReceivedRef = useRef(false);
  /** 当前轮 turnId，用于过滤迟到的 TTS 包 */
  const activeTtsTurnIdRef = useRef<string | null>(null);
  /** 当前轮是否已触发浏览器朗读，防止重复播放 */
  const browserTtsStartedRef = useRef(false);
  const speakFallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const setMutedRef = useRef<(muted: boolean) => void>(() => {});

  // 唯一稳定 key — 当前 streaming 的 turn 的 id
  const pendingTurnIdRef = useRef<string>("");
  // 防止重复跳转报告页
  const navigatedToReportRef = useRef(false);
  // 流式文本 ref — 在 agent.text.delta 中直接更新，避免 useEffect 滞后
  const streamingTextRef = useRef("");

  // ---- 自动滚动到底部（useLayoutEffect 在 DOM 更新后同步执行，避免闪烁） ----
  const scrollToBottom = useCallback(() => {
    // requestAnimationFrame 确保在浏览器绘制前完成滚动
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
    });
  }, []);

  useLayoutEffect(() => {
    scrollToBottom();
  }, [turns, streamingAiText, streamingUserText, scrollToBottom]);

  // ---- TTS 播放（队列 + 浏览器降级） ----
  const finishSpeaking = useCallback(() => {
    setIsAiSpeaking(false);
    setTimeout(() => setMutedRef.current(false), 500);
  }, []);

  const playNextBrowserSpeech = useCallback(() => {
    if (
      typeof window === "undefined" ||
      !window.speechSynthesis ||
      isBrowserSpeakingRef.current ||
      browserSpeechQueueRef.current.length === 0
    ) {
      return;
    }
    isBrowserSpeakingRef.current = true;
    browserTtsStartedRef.current = true;
    setMutedRef.current(true);
    setIsAiSpeaking(true);

    const clause = browserSpeechQueueRef.current.shift()!;
    const utterance = new SpeechSynthesisUtterance(clause);
    utterance.lang = "en-US";
    utterance.onend = () => {
      isBrowserSpeakingRef.current = false;
      if (browserSpeechQueueRef.current.length > 0) {
        playNextBrowserSpeech();
      } else if (!isPlayingQueueRef.current && audioQueueRef.current.length === 0) {
        finishSpeaking();
      }
    };
    utterance.onerror = () => {
      isBrowserSpeakingRef.current = false;
      if (browserSpeechQueueRef.current.length > 0) {
        playNextBrowserSpeech();
      } else {
        finishSpeaking();
      }
    };
    window.speechSynthesis.speak(utterance);
  }, [finishSpeaking]);

  const enqueueBrowserSpeech = useCallback((text: string) => {
    const clause = text.trim();
    if (!clause || typeof window === "undefined" || !window.speechSynthesis) return;
    browserSpeechQueueRef.current.push(clause);
    playNextBrowserSpeech();
  }, [playNextBrowserSpeech]);

  const playNextInQueue = useCallback(() => {
    if (isPlayingQueueRef.current || audioQueueRef.current.length === 0) return;
    isPlayingQueueRef.current = true;
    setMutedRef.current(true);
    setIsAiSpeaking(true);

    const base64Payload = audioQueueRef.current.shift()!;
    try {
      const binary = atob(base64Payload);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: "audio/mp3" });
      const url = URL.createObjectURL(blob);

      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.onended = null;
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch((err) => {
        console.warn("[Voice] TTS 播放被阻止:", err);
        URL.revokeObjectURL(url);
        isPlayingQueueRef.current = false;
        if (audioQueueRef.current.length > 0) {
          playNextInQueue();
        } else {
          finishSpeaking();
        }
      });
      audio.onended = () => {
        URL.revokeObjectURL(url);
        isPlayingQueueRef.current = false;
        if (audioQueueRef.current.length > 0) {
          playNextInQueue();
        } else {
          finishSpeaking();
        }
      };
    } catch (err) {
      console.warn("[Voice] TTS 解码失败:", err);
      isPlayingQueueRef.current = false;
      if (audioQueueRef.current.length > 0) {
        playNextInQueue();
      } else {
        finishSpeaking();
      }
    }
  }, [finishSpeaking]);

  const resetTurnAudio = useCallback(() => {
    ttsReceivedRef.current = false;
    browserTtsStartedRef.current = false;
    streamingTextRef.current = "";
    audioQueueRef.current = [];
    browserSpeechQueueRef.current = [];
    isBrowserSpeakingRef.current = false;
    isPlayingQueueRef.current = false;
    if (speakFallbackTimerRef.current) {
      clearTimeout(speakFallbackTimerRef.current);
      speakFallbackTimerRef.current = null;
    }
    if (typeof window !== "undefined") {
      window.speechSynthesis?.cancel();
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onended = null;
      audioRef.current = null;
    }
  }, []);

  const enqueueAudio = useCallback((base64Payload: string) => {
    ttsReceivedRef.current = true;
    browserTtsStartedRef.current = true;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (speakFallbackTimerRef.current) {
      clearTimeout(speakFallbackTimerRef.current);
      speakFallbackTimerRef.current = null;
    }
    audioQueueRef.current.push(base64Payload);
    playNextInQueue();
  }, [playNextInQueue]);

  // ---- 展示会话提示条，默认 5 秒后自动消失 ----
  const showSessionNotice = useCallback(
    (
      kind: SessionNoticeKind,
      message: string,
      options?: { title?: string; autoHideMs?: number }
    ) => {
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
      }
      setSessionNotice({ kind, message, title: options?.title });
      noticeTimerRef.current = setTimeout(() => {
        setSessionNotice(null);
        noticeTimerRef.current = null;
      }, options?.autoHideMs ?? 5000);
    },
    []
  );

  // ---- 跳转课后报告页 ----
  const navigateToReport = useCallback(async () => {
    if (navigatedToReportRef.current) return;
    navigatedToReportRef.current = true;
    try {
      await finishSession(session.sessionId);
    } catch (err) {
      console.warn("[Voice] finishSession:", err);
    }
    router.push(`/reports/${session.sessionId}`);
  }, [router, session.sessionId]);

  // ---- WebSocket 消息处理 ----
  const handleWsMessage = useCallback(
    (msg: WsServerMessage) => {
      switch (msg.type) {
        case "asr.partial": {
          setStreamingUserText(msg.partialTranscript);
          break;
        }

        case "asr.final": {
          // 立即将用户消息加入 turns（不等 AI 回复！）
          const userText = msg.finalTranscript;
          const stableId = nextId();
          const newTurn: TurnRecord = {
            id: stableId,
            turnId: msg.turnId,
            userText,
            aiText: "",
          };
          setTurns((p) => [...p, newTurn]);
          pendingTurnIdRef.current = stableId;
          setStreamingTurnId(msg.turnId);
          setStreamingAiText("");
          resetTurnAudio();
          activeTtsTurnIdRef.current = msg.turnId;
          setStreamingUserText("");
          setCorrection(undefined);
          break;
        }

        case "asr.no_result": {
          setStreamingUserText("");
          if (msg.reason === "non_english") {
            showSessionNotice("warning", t("voice.hint.englishOnly"), {
              title: t("voice.englishOnlyTip"),
              autoHideMs: 6000,
            });
          } else {
            showSessionNotice("warning", t("voice.hint.noSpeech"), {
              autoHideMs: 4000,
            });
          }
          break;
        }

        case "agent.text.delta": {
          streamingTextRef.current += msg.delta;
          setStreamingAiText(streamingTextRef.current);
          break;
        }

        case "agent.text.done": {
          const finalText = streamingTextRef.current;
          const stableId = pendingTurnIdRef.current;
          setTurns((p) =>
            p.map((t) =>
              t.id === stableId ? { ...t, aiText: finalText } : t
            )
          );
          streamingTextRef.current = "";
          setStreamingAiText("");
          setStreamingTurnId(null);
          pendingTurnIdRef.current = "";
          // 朗读仅由 tts.audio.delta 或 tts.unavailable 触发一次
          break;
        }

        case "tts.audio.delta": {
          if (activeTtsTurnIdRef.current && msg.turnId !== activeTtsTurnIdRef.current) {
            break;
          }
          enqueueAudio(msg.payload);
          break;
        }

        case "tts.unavailable": {
          if (activeTtsTurnIdRef.current && msg.turnId !== activeTtsTurnIdRef.current) {
            break;
          }
          enqueueBrowserSpeech(msg.text);
          break;
        }

        case "correction.light": {
          if (!correctionEnabledRef.current) break;
          const tip = { original: msg.originalText, corrected: msg.correctedText };
          setCorrection(tip);
          setToastTip({
            original: msg.originalText,
            corrected: msg.correctedText,
            spokenTip: msg.spokenTip,
          });
          const sid = pendingTurnIdRef.current;
          setTurns((p) =>
            p.map((t) => (t.id === sid ? { ...t, correction: tip } : t))
          );
          break;
        }

        case "correction.state": {
          correctionEnabledRef.current = msg.enabled;
          setCorrectionEnabled(msg.enabled);
          if (!msg.enabled) {
            setToastTip(null);
            setCorrection(undefined);
          }
          // 首次连接同步不弹提示，仅用户手动切换时反馈
          if (!correctionInitRef.current) {
            correctionInitRef.current = true;
          } else {
            showSessionNotice(
              "info",
              msg.enabled ? t("voice.correctionEnabledDesc") : t("voice.correctionDisabledDesc"),
              {
                title: msg.enabled
                  ? t("voice.correctionEnabled")
                  : t("voice.correctionDisabled"),
                autoHideMs: 3500,
              }
            );
          }
          break;
        }

        case "analysis.counter": {
          setFillerCounts(msg.fillerCounts);
          break;
        }

        case "control.finish": {
          navigateToReport();
          break;
        }

        case "asr.unavailable": {
          setInputMode("text");
          showSessionNotice("warning", t("voice.hint.asrUnavailable"), {
            autoHideMs: 6000,
          });
          break;
        }

        case "error": {
          console.error("[Voice] Server error:", msg.message);
          showSessionNotice("error", t("voice.hint.serverError"), {
            autoHideMs: 5000,
          });
          break;
        }
      }
    },
    [enqueueAudio, enqueueBrowserSpeech, navigateToReport, resetTurnAudio, showSessionNotice, t]
  );

  // ---- WebSocket ----
  const { status: wsStatus, sendMessage } = useWebSocket({
    url: session.websocketUrl,
    onMessage: handleWsMessage,
  });

  // ---- 麦克风 ----
  const {
    status: micStatus,
    isRecording,
    startRecording,
    stopRecording,
    setMuted,
    error: micError,
  } = useMicrophone({
    onAudioChunk: useCallback(
      (base64Pcm: string, sequenceId: number) => {
        if (sequenceId % 50 === 1) {
          console.log(`[Voice] Audio #${sequenceId} size=${base64Pcm.length}b`);
        }
        if (!sendMessage({
          type: "audio.input", sessionId: session.sessionId,
          sequenceId, timestampMs: Date.now(),
          codec: "pcm16", sampleRate: 16000, payload: base64Pcm,
        }) && sequenceId % 50 === 1) {
          console.warn("[Voice] WS 未连接，音频未发送");
        }
      },
      [sendMessage, session.sessionId]
    ),
  });
  setMutedRef.current = setMuted;

  // ---- 发送文本 ----
  const sendTextMessage = useCallback(() => {
    const text = textInput.trim();
    if (!text || wsStatus !== "connected") return;

    // 立即显示用户消息（不等后端回复！）
    const stableId = nextId();
    // 用临时 turnId，等后端确认后再更新
    const tempTurnId = `turn_text_${Date.now()}`;
    const newTurn: TurnRecord = {
      id: stableId,
      turnId: tempTurnId,
      userText: text,
      aiText: "",
    };
    setTurns((p) => [...p, newTurn]);
    pendingTurnIdRef.current = stableId;
    setStreamingTurnId(tempTurnId);
    setStreamingAiText("");
    resetTurnAudio();
    activeTtsTurnIdRef.current = tempTurnId;

    sendMessage({
      type: "text.input", sessionId: session.sessionId, text,
    });
    setTextInput("");
  }, [textInput, wsStatus, sendMessage, session.sessionId, resetTurnAudio]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendTextMessage();
      }
    },
    [sendTextMessage]
  );

  // ---- 麦克风开关（async，确保状态精确流转） ----
  const toggleMic = useCallback(async () => {
    if (isRecording) {
      stopRecording();
      setVoiceReady(false);
    } else {
      setInputMode("voice");
      setVoiceReady(false);
      micPrepStartRef.current = Date.now();
      try {
        await startRecording();
        // startRecording 成功后 micStatus 会变为 "active"
        // voiceReady 由下方的 useEffect 根据 micStatus 同步设置
      } catch {
        // 权限拒绝已在 useMicrophone 中处理
        setVoiceReady(false);
      }
    }
  }, [isRecording, startRecording, stopRecording]);

  // ---- 结束 ----
  const handleEndSession = useCallback(() => {
    setIsEnding(true);
    sendMessage({ type: "control.finish", sessionId: session.sessionId, reason: "userFinished" });
    // WS 可能已断开，直接调用 REST 并跳转报告页
    navigateToReport();
  }, [sendMessage, session.sessionId, navigateToReport]);

  // ---- 实时轻纠正开关 ----
  const toggleCorrection = useCallback(() => {
    const next = !correctionEnabledRef.current;
    correctionEnabledRef.current = next;
    setCorrectionEnabled(next);
    if (!next) {
      setToastTip(null);
      setCorrection(undefined);
    }
    sendMessage({
      type: "control.correction",
      sessionId: session.sessionId,
      enabled: next,
    });
  }, [sendMessage, session.sessionId]);

  // ---- 模式切换 ----
  const switchToText = useCallback(() => {
    if (isRecording) stopRecording();
    setVoiceReady(false);
    setInputMode("text");
  }, [isRecording, stopRecording]);

  const switchToVoice = useCallback(async () => {
    setInputMode("voice");
    setVoiceReady(false);
    micPrepStartRef.current = Date.now();
    try {
      await startRecording();
    } catch {
      setVoiceReady(false);
    }
  }, [startRecording]);

  // ---- 麦克风就绪状态同步 + 5 秒超时降级 ----
  useEffect(() => {
    // WS 已连接 + 麦克风 active → 真正就绪
    if (wsStatus === "connected" && micStatus === "active") {
      setVoiceReady(true);
      micPrepStartRef.current = 0;
    } else if (micStatus === "idle" || micStatus === "error" || micStatus === "denied") {
      setVoiceReady(false);
    }
  }, [wsStatus, micStatus]);

  // 默认语音模式：WS 连接成功后自动开启麦克风
  useEffect(() => {
    if (
      inputMode === "voice" &&
      wsStatus === "connected" &&
      micStatus === "idle" &&
      !isRecording
    ) {
      micPrepStartRef.current = Date.now();
      startRecording().catch(() => setVoiceReady(false));
    }
  }, [inputMode, wsStatus, micStatus, isRecording, startRecording]);

  // 5 秒超时：麦克风一直未就绪 → 自动切回文本模式
  useEffect(() => {
    if (inputMode !== "voice" || voiceReady) return;
    if (micPrepStartRef.current === 0) return;

    const timer = setInterval(() => {
      const elapsed = Date.now() - micPrepStartRef.current;
      if (elapsed > 5000 && !voiceReady) {
        console.warn("[Voice] Mic preparation timeout (>5s), falling back to text mode");
        if (isRecording) stopRecording();
        setVoiceReady(false);
        setInputMode("text");
        micPrepStartRef.current = 0;
      }
    }, 500);

    return () => clearInterval(timer);
  }, [inputMode, voiceReady, isRecording, stopRecording]);

  // 卸载时清理提示定时器
  useEffect(() => {
    return () => {
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
      }
    };
  }, []);

  // ---- 派生最终连接状态（WebSocket + 麦克风 + voiceReady 三重确认） ----
  // 状态机严格顺序：disconnected → connecting → connected → mic_ready
  const derivedStatus: ConnectionStatus = wsStatus === "error" || micStatus === "denied"
    ? "error"
    : wsStatus === "connecting"
      ? "connecting"
      : voiceReady
        ? "mic_ready"
        : wsStatus === "connected"
          ? (inputMode === "voice" && micStatus === "requesting" ? "connecting" : "connected")
          : wsStatus;

  // ---- 连接状态文案（按状态机精准显示，避免虚假"已连接"误导用户） ----
  const statusText = (() => {
    if (derivedStatus === "error") {
      return micStatus === "denied" ? t("voice.micDenied") : t("voice.hint.serverError");
    }
    if (derivedStatus === "connecting") {
      return inputMode === "voice" ? t("voice.status.preparingMic") : t("session.connecting");
    }
    if (derivedStatus === "connected") {
      return inputMode === "voice"
        ? t("voice.status.connectedVoice")
        : t("voice.status.connectedText");
    }
    if (derivedStatus === "mic_ready") {
      return t("session.connected");
    }
    return t("session.disconnected");
  })();

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* ---- Header ---- */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6">
          <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors">
            {t("scene.backHome")}
          </Link>
          <div className="flex items-center gap-4">
            {/* 语气词计数器 */}
            {Object.keys(fillerCounts).length > 0 && (
              <span className="text-xs text-zinc-400">
                {Object.entries(fillerCounts)
                  .filter(([, c]) => c > 0)
                  .map(([w, c]) => `${w}:${c}`)
                  .join(" ")}
              </span>
            )}
            {!correctionEnabled && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                {t("voice.correctionPausedBadge")}
              </span>
            )}
            {isAiSpeaking && (
              <span className="text-xs text-indigo-500 animate-pulse">
                {t("voice.aiSpeaking")}
              </span>
            )}
            <StatusBadge status={derivedStatus} />
            <span className="text-xs text-zinc-400">
              {t("session.id")}: {session.sessionId.slice(0, 8)}…
            </span>
          </div>
        </div>
      </header>

      {/* ---- 聊天区 ---- */}
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-6">
        <div ref={chatContainerRef} className="flex-1 space-y-3 overflow-y-auto py-6">

          {/* 实时 ASR 字幕 */}
          {streamingUserText && (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-md bg-indigo-400/60 px-4 py-2.5 text-sm text-white">
                <p className="mb-0.5 text-xs font-medium opacity-70">🎤 {t("voice.userSaid")}</p>
                {streamingUserText}
              </div>
            </div>
          )}

          {/* 空状态 */}
          {turns.length === 0 && !streamingUserText && (
            <div className="py-20 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 text-2xl dark:bg-indigo-900/30">
                🎙️
              </div>
              <p className="text-sm text-zinc-500">{statusText}</p>
              {inputMode === "voice" && derivedStatus === "mic_ready" && (
                <p className="mx-auto mt-3 max-w-sm text-xs text-amber-600 dark:text-amber-400">
                  {t("voice.englishOnlyTip")}
                </p>
              )}
              {micError && (
                <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">{micError}</p>
              )}
            </div>
          )}

          {/* 已完成的轮次 + 正在流式的 turn */}
          {turns.map((turn) => {
            const isStreaming = turn.id === pendingTurnIdRef.current && !!streamingTurnId;
            return (
              <div key={turn.id} className="space-y-2">
                {/* 用户消息 — 立即出现 */}
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-br-md bg-indigo-500 px-4 py-2.5 text-sm text-white">
                    <p className="mb-0.5 text-xs font-medium opacity-70">{t("voice.userSaid")}</p>
                    {turn.userText}
                  </div>
                </div>

                {/* AI 回复 — 流式或完成 */}
                {(isStreaming ? streamingAiText : turn.aiText) && (
                  <div className="flex justify-start">
                    <div
                      className={`max-w-[80%] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm shadow-sm ${
                        isStreaming
                          ? "bg-indigo-50 text-zinc-700 dark:bg-indigo-900/20 dark:text-zinc-300"
                          : "bg-white text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
                      }`}
                    >
                      <p className="mb-0.5 text-xs font-medium text-zinc-400">{t("voice.aiReplied")}</p>
                      {isStreaming ? streamingAiText : turn.aiText}
                      {isStreaming && (
                        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-indigo-500" />
                      )}
                    </div>
                  </div>
                )}

                {/* 轻纠正 */}
                {turn.correction && (
                  <div className="flex justify-center">
                    <div className="max-w-[90%] rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      <span className="font-semibold">{t("voice.correction")}: </span>
                      <span className="line-through">{turn.correction.original}</span>
                      {" → "}
                      <span className="font-medium text-emerald-700 dark:text-emerald-400">
                        {turn.correction.corrected}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          <div ref={messagesEndRef} />
        </div>

        {/* ---- 底部输入 ---- */}
        <div className="sticky bottom-0 border-t border-zinc-200 bg-white/90 py-4 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/90">
          {/* 会话提示条 */}
          {sessionNotice && (
            <div className="mb-3">
              <SessionNoticeBanner
                kind={sessionNotice.kind}
                title={sessionNotice.title}
                message={sessionNotice.message}
                onDismiss={() => {
                  if (noticeTimerRef.current) {
                    clearTimeout(noticeTimerRef.current);
                    noticeTimerRef.current = null;
                  }
                  setSessionNotice(null);
                }}
              />
            </div>
          )}

          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex gap-2">
              <button onClick={switchToText}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  inputMode === "text"
                    ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                    : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400"
                }`}>{t("voice.textMode")}</button>
              <button onClick={switchToVoice}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  inputMode === "voice"
                    ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                    : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400"
                }`}>{t("voice.audioMode")}</button>
              </div>
              {/* 实时轻纠正开关 */}
              <div className="flex flex-col gap-0.5">
                <label className="flex cursor-pointer items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={correctionEnabled}
                    onChange={toggleCorrection}
                    className="h-3.5 w-3.5 rounded border-zinc-300 text-indigo-500 focus:ring-indigo-500"
                  />
                  <span className="text-xs text-zinc-500">{t("config.lightCorrection")}</span>
                </label>
                <p className="pl-5 text-[10px] leading-snug text-zinc-400">
                  {correctionEnabled
                    ? t("voice.correctionEnabledDesc")
                    : t("voice.correctionDisabledDesc")}
                </p>
              </div>
            </div>
            <button onClick={handleEndSession} disabled={isEnding}
              className="rounded-full bg-red-500 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50">
              {isEnding ? t("voice.ending") : t("voice.endSession")}
            </button>
          </div>

          {/* 文本输入 */}
          {inputMode === "text" && (
            <div className="flex gap-2">
              <input type="text" value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t("voice.typeMessage")}
                disabled={wsStatus !== "connected"}
                className="flex-1 rounded-xl border border-zinc-300 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder-zinc-400 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100" />
              <button onClick={sendTextMessage}
                disabled={!textInput.trim() || wsStatus !== "connected"}
                className="rounded-xl bg-indigo-500 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-50">
                {t("voice.send")}
              </button>
            </div>
          )}

          {/* 语音输入 */}
          {inputMode === "voice" && (
            <div className="flex items-center justify-center gap-4">
              <button onClick={toggleMic}
                disabled={micStatus === "denied" || isAiSpeaking}
                className={`flex h-14 w-14 items-center justify-center rounded-full text-xl transition-all ${
                  isRecording
                    ? "animate-pulse bg-red-500 text-white shadow-lg shadow-red-500/30"
                    : "bg-indigo-500 text-white shadow-lg hover:bg-indigo-600"
                } disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700`}>
                {isRecording ? "⏹" : "🎤"}
              </button>
              <span className="text-xs text-zinc-500">
                {isAiSpeaking
                  ? t("voice.aiSpeaking")
                  : isRecording
                    ? t("voice.listening")
                    : micStatus === "denied"
                      ? t("voice.micDenied")
                      : t("voice.startMic")}
              </span>
            </div>
          )}
        </div>
      </main>

      {/* 非模态轻纠正 Toast */}
      <CorrectionToast tip={toastTip} />
    </div>
  );
}
