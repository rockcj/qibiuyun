"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";
import { useMicrophone } from "@/hooks/useMicrophone";
import { useWebSocket, type ConnectionStatus } from "@/hooks/useWebSocket";
import type { CreateSessionResponse, TurnRecord, WsServerMessage } from "@/types/api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface VoiceSessionPanelProps {
  session: CreateSessionResponse;
}

// ---------------------------------------------------------------------------
// 连接状态指示器
// ---------------------------------------------------------------------------
function StatusBadge({ status }: { status: ConnectionStatus }) {
  const colors: Record<ConnectionStatus, string> = {
    connected: "bg-emerald-500",
    connecting: "bg-amber-500 animate-pulse",
    disconnected: "bg-zinc-400",
  };
  return (
    <span className="flex items-center gap-1.5 text-xs text-zinc-500">
      <span className={`h-2 w-2 rounded-full ${colors[status]}`} />
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// 主组件
// ---------------------------------------------------------------------------
export default function VoiceSessionPanel({ session }: VoiceSessionPanelProps) {
  const { t } = useLocale();
  const router = useRouter();

  // ---- 输入模式 ----
  const [inputMode, setInputMode] = useState<"text" | "voice">("text");
  const [textInput, setTextInput] = useState("");

  // ---- 对话状态 ----
  const [turns, setTurns] = useState<TurnRecord[]>([]);
  const [currentTurnId, setCurrentTurnId] = useState<string | null>(null);
  const [streamingAiText, setStreamingAiText] = useState("");
  const [correction, setCorrection] = useState<
    { original: string; corrected: string } | undefined
  >();
  const [isEnding, setIsEnding] = useState(false);

  // ---- 引用（避免闭包问题） ----
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const turnBufferRef = useRef<{
    turnId: string;
    userText: string;
    aiText: string;
    correction?: { original: string; corrected: string };
  } | null>(null);
  const streamRef = useRef(""); // 累积流式文本，避免闭包陈旧值

  // ---- 自动滚动到底部 ----
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streamingAiText]);

  // ---- 播放 TTS 音频 ----
  const playAudio = useCallback((base64Payload: string) => {
    try {
      const binary = atob(base64Payload);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: "audio/mp3" });
      const url = URL.createObjectURL(blob);

      if (audioRef.current) {
        audioRef.current.pause();
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch(() => {
        /* 自动播放可能被浏览器拦截 */
      });
      audio.onended = () => URL.revokeObjectURL(url);
    } catch {
      /* 音频解码失败 */
    }
  }, []);

  // ---- WebSocket 消息处理（不依赖 state，通过 ref 通信） ----
  const handleWsMessage = useCallback(
    (msg: WsServerMessage) => {
      switch (msg.type) {
        case "asr.final": {
          // 提交上一轮缓冲（如果有）
          const prev = turnBufferRef.current;
          if (prev && prev.turnId !== msg.turnId) {
            setTurns((p) => [
              ...p,
              {
                turnId: prev.turnId,
                userText: prev.userText,
                aiText: prev.aiText || streamRef.current,
                correction: prev.correction,
              },
            ]);
          }
          // 开始新轮次
          turnBufferRef.current = {
            turnId: msg.turnId,
            userText: msg.finalTranscript,
            aiText: "",
          };
          streamRef.current = "";
          setCurrentTurnId(msg.turnId);
          setStreamingAiText("");
          setCorrection(undefined);
          break;
        }

        case "agent.text.delta": {
          streamRef.current += msg.delta;
          setStreamingAiText(streamRef.current);
          break;
        }

        case "agent.text.done": {
          const buf = turnBufferRef.current;
          const finalText = streamRef.current;
          if (buf) {
            buf.aiText = finalText;
            setTurns((p) => [
              ...p,
              {
                turnId: buf.turnId,
                userText: buf.userText,
                aiText: finalText,
                correction: buf.correction,
              },
            ]);
            turnBufferRef.current = null;
          }
          streamRef.current = "";
          setStreamingAiText("");
          setCurrentTurnId(null);
          break;
        }

        case "tts.audio.delta": {
          playAudio(msg.payload);
          break;
        }

        case "correction.light": {
          const tip = {
            original: msg.originalText,
            corrected: msg.correctedText,
          };
          setCorrection(tip);
          if (turnBufferRef.current) {
            turnBufferRef.current.correction = tip;
          }
          break;
        }

        case "control.finish": {
          router.push(`/reports/${session.sessionId}`);
          break;
        }

        case "asr.unavailable": {
          // ASR 不可用 → 自动切文本模式
          console.warn("[Voice] ASR unavailable, switching to text mode");
          setInputMode("text");
          break;
        }

        case "error": {
          console.error("[Voice] Server error:", msg.message);
          break;
        }

        case "pong":
          // 心跳响应，忽略
          break;
      }
    },
    [playAudio, router, session.sessionId]
  );

  // ---- WebSocket 连接 ----
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
    error: micError,
  } = useMicrophone({
    onAudioChunk: useCallback(
      (base64Pcm: string, sequenceId: number) => {
        // 每50片打印一次，方便确认麦克风是否在工作
        if (sequenceId % 50 === 1) {
          console.log(`[Voice] Audio chunk #${sequenceId}, size=${base64Pcm.length}b`);
        }
        sendMessage({
          type: "audio.input",
          sessionId: session.sessionId,
          sequenceId,
          timestampMs: Date.now(),
          codec: "pcm16",
          sampleRate: 16000,
          payload: base64Pcm,
        });
      },
      [sendMessage, session.sessionId]
    ),
  });

  // ---- 发送文本消息 ----
  const sendTextMessage = useCallback(() => {
    const text = textInput.trim();
    if (!text || wsStatus !== "connected") return;

    sendMessage({
      type: "text.input",
      sessionId: session.sessionId,
      text,
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

  // ---- 麦克风切换 ----
  const toggleMic = useCallback(async () => {
    if (isRecording) {
      stopRecording();
    } else {
      setInputMode("voice");
      await startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // ---- 结束会话 ----
  const handleEndSession = useCallback(() => {
    setIsEnding(true);
    sendMessage({
      type: "control.finish",
      sessionId: session.sessionId,
      reason: "userFinished",
    });
  }, [sendMessage, session.sessionId]);

  // ---- 模式切换 ----
  const switchToText = useCallback(() => {
    if (isRecording) stopRecording();
    setInputMode("text");
  }, [isRecording, stopRecording]);

  const switchToVoice = useCallback(async () => {
    setInputMode("voice");
    await startRecording();
  }, [startRecording]);

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* ---- Header ---- */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6">
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
          >
            {t("scene.backHome")}
          </Link>
          <div className="flex items-center gap-4">
            <StatusBadge status={wsStatus} />
            <span className="text-xs text-zinc-400">
              {t("session.id")}: {session.sessionId.slice(0, 8)}…
            </span>
          </div>
        </div>
      </header>

      {/* ---- 对话区域 ---- */}
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-6">
        <div className="flex-1 space-y-4 overflow-y-auto py-6">
          {/* 空状态 */}
          {turns.length === 0 && !currentTurnId && (
            <div className="py-20 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 text-2xl dark:bg-indigo-900/30">
                🎙️
              </div>
              <p className="text-sm text-zinc-500">
                {wsStatus === "connected"
                  ? t("session.connected")
                  : wsStatus === "connecting"
                    ? t("session.connecting")
                    : t("session.disconnected")}
              </p>
              {micError && (
                <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                  {micError}
                </p>
              )}
            </div>
          )}

          {/* 已完成的轮次 */}
          {turns.map((turn) => (
            <div key={turn.turnId} className="space-y-2">
              {/* 用户消息 */}
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-br-md bg-indigo-500 px-4 py-2.5 text-sm text-white">
                  <p className="mb-0.5 text-xs font-medium opacity-70">
                    {t("voice.userSaid")}
                  </p>
                  {turn.userText}
                </div>
              </div>

              {/* AI 回复 */}
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 text-sm text-zinc-800 shadow-sm dark:bg-zinc-800 dark:text-zinc-200">
                  <p className="mb-0.5 text-xs font-medium text-zinc-400">
                    {t("voice.aiReplied")}
                  </p>
                  {turn.aiText}
                </div>
              </div>

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
          ))}

          {/* 当前流式生成的 AI 回复 */}
          {currentTurnId && streamingAiText && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 text-sm text-zinc-800 shadow-sm dark:bg-zinc-800 dark:text-zinc-200">
                <p className="mb-0.5 text-xs font-medium text-zinc-400">
                  {t("voice.aiReplied")}
                </p>
                {streamingAiText}
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-indigo-500" />
              </div>
            </div>
          )}

          {correction && currentTurnId && (
            <div className="flex justify-center">
              <div className="max-w-[90%] rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                <span className="font-semibold">{t("voice.correction")}: </span>
                <span className="line-through">{correction.original}</span>
                {" → "}
                <span className="font-medium text-emerald-700 dark:text-emerald-400">
                  {correction.corrected}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ---- 底部输入区域 ---- */}
        <div className="sticky bottom-0 border-t border-zinc-200 bg-white/90 py-4 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/90">
          {/* 模式切换 + 结束 */}
          <div className="mb-3 flex items-center justify-between">
            <div className="flex gap-2">
              <button
                onClick={switchToText}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  inputMode === "text"
                    ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                    : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400"
                }`}
              >
                {t("voice.textMode")}
              </button>
              <button
                onClick={switchToVoice}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  inputMode === "voice"
                    ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                    : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400"
                }`}
              >
                {t("voice.audioMode")}
              </button>
            </div>

            <button
              onClick={handleEndSession}
              disabled={isEnding}
              className="rounded-full bg-red-500 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
            >
              {isEnding ? t("voice.ending") : t("voice.endSession")}
            </button>
          </div>

          {/* 文本输入栏 */}
          {inputMode === "text" && (
            <div className="flex gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t("voice.typeMessage")}
                disabled={wsStatus !== "connected"}
                className="flex-1 rounded-xl border border-zinc-300 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder-zinc-400 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              />
              <button
                onClick={sendTextMessage}
                disabled={!textInput.trim() || wsStatus !== "connected"}
                className="rounded-xl bg-indigo-500 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("voice.send")}
              </button>
            </div>
          )}

          {/* 语音输入按钮 */}
          {inputMode === "voice" && (
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={toggleMic}
                disabled={micStatus === "denied"}
                className={`flex h-14 w-14 items-center justify-center rounded-full text-xl transition-all ${
                  isRecording
                    ? "animate-pulse bg-red-500 text-white shadow-lg shadow-red-500/30"
                    : "bg-indigo-500 text-white shadow-lg hover:bg-indigo-600"
                } disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700`}
              >
                {isRecording ? "⏹" : "🎤"}
              </button>
              <span className="text-xs text-zinc-500">
                {isRecording
                  ? t("voice.stopMic")
                  : micStatus === "denied"
                    ? t("voice.micDenied")
                    : t("voice.startMic")}
              </span>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
