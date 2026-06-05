"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";
import { useMicrophone } from "@/hooks/useMicrophone";
import { useWebSocket, type ConnectionStatus } from "@/hooks/useWebSocket";
import type { CreateSessionResponse, TurnRecord, WsServerMessage } from "@/types/api";

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
  const [inputMode, setInputMode] = useState<"text" | "voice">("text");
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
  const [isEnding, setIsEnding] = useState(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const [streamingUserText, setStreamingUserText] = useState("");

  // ---- Refs ----
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const setMutedRef = useRef<(muted: boolean) => void>(() => {});

  // 唯一稳定 key — 当前 streaming 的 turn 的 id
  const pendingTurnIdRef = useRef<string>("");
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

  // ---- TTS 播放 ----
  const playAudio = useCallback((base64Payload: string) => {
    setMutedRef.current(true);
    try {
      const binary = atob(base64Payload);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: "audio/mp3" });
      const url = URL.createObjectURL(blob);

      if (audioRef.current) { audioRef.current.pause(); audioRef.current.onended = null; }
      setIsAiSpeaking(true);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch(() => {});
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setIsAiSpeaking(false);
        setTimeout(() => setMutedRef.current(false), 500);
      };
    } catch {
      setIsAiSpeaking(false);
      setTimeout(() => setMutedRef.current(false), 500);
    }
  }, []);

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
          setStreamingUserText("");
          setCorrection(undefined);
          break;
        }

        case "asr.no_result": {
          setStreamingUserText("(未检测到语音，请重试)");
          setTimeout(() => setStreamingUserText(""), 2000);
          break;
        }

        case "agent.text.delta": {
          // 同步更新 state 和 ref（避免 useEffect 滞后导致 done 时拿到旧值）
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
          break;
        }

        case "tts.audio.delta": {
          playAudio(msg.payload);
          break;
        }

        case "correction.light": {
          const tip = { original: msg.originalText, corrected: msg.correctedText };
          setCorrection(tip);
          // 更新对应 turn 的 correction
          const sid = pendingTurnIdRef.current;
          setTurns((p) =>
            p.map((t) => (t.id === sid ? { ...t, correction: tip } : t))
          );
          break;
        }

        case "control.finish": {
          router.push(`/reports/${session.sessionId}`);
          break;
        }

        case "asr.unavailable": {
          setInputMode("text");
          break;
        }

        case "error": {
          console.error("[Voice] Server error:", msg.message);
          break;
        }
      }
    },
    [playAudio, router, session.sessionId]
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
        sendMessage({
          type: "audio.input", sessionId: session.sessionId,
          sequenceId, timestampMs: Date.now(),
          codec: "pcm16", sampleRate: 16000, payload: base64Pcm,
        });
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

    sendMessage({
      type: "text.input", sessionId: session.sessionId, text,
    });
    setTextInput("");
  }, [textInput, wsStatus, sendMessage, session.sessionId]);

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
      return micStatus === "denied"
        ? "麦克风权限被拒绝，请使用文本输入或授权麦克风"
        : "连接失败，请刷新页面重试";
    }
    if (derivedStatus === "connecting") {
      return inputMode === "voice" ? "正在准备麦克风…" : "正在建立连接…";
    }
    if (derivedStatus === "connected") {
      return inputMode === "voice" ? "连接已建立，正在准备麦克风…" : "已连接，请输入文字开始对话";
    }
    if (derivedStatus === "mic_ready") {
      return "已连接，开始对话吧";
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
          <div className="mb-3 flex items-center justify-between">
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
                {isAiSpeaking ? "🔊 AI 正在回复…"
                  : isRecording ? t("voice.stopMic")
                  : micStatus === "denied" ? t("voice.micDenied")
                  : t("voice.startMic")}
              </span>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
