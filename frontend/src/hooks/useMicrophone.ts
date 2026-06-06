/** 麦克风 Hook – PCM 采集 + 客户端 VAD + 静音控制 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const PCM_CONFIG = {
  sampleRate: 16000,
  channelCount: 1,
  samplesPerChunk: 1024, // 64ms @ 16kHz
  /** RMS 能量阈值：低于此值视为静音帧 */
  rmsThreshold: 0.008,
  /** 客户端检测到连续静音多久视为用户说完（毫秒） */
  silenceEndMs: 500,
};

export type MicStatus = "idle" | "requesting" | "active" | "error" | "denied";

interface UseMicrophoneOptions {
  onAudioChunk?: (base64Pcm: string, sequenceId: number) => void;
  /** 客户端 VAD 判定用户说完（0.5s 静音） */
  onTurnEnd?: () => void;
  onError?: (error: string) => void;
}

interface UseMicrophoneReturn {
  status: MicStatus;
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  /** 静音开关：true=暂停发送音频，false=恢复发送 */
  setMuted: (muted: boolean) => void;
  error: string | null;
}

export function useMicrophone(options: UseMicrophoneOptions = {}): UseMicrophoneReturn {
  const { onAudioChunk, onTurnEnd, onError } = options;

  const [status, setStatus] = useState<MicStatus>("idle");
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const sequenceRef = useRef(0);
  const recordingRef = useRef(false);

  // 静音控制：TTS / AI 处理期间为 true
  const mutedRef = useRef(false);
  const setMuted = useCallback((muted: boolean) => {
    mutedRef.current = muted;
    if (muted) {
      speechActiveRef.current = false;
      silenceFramesRef.current = 0;
      console.log("[Mic] Muted");
    } else {
      console.log("[Mic] Unmuted");
    }
  }, []);

  // 客户端 VAD：一轮采集中 + 句末静音帧计数
  const speechActiveRef = useRef(false);
  const silenceFramesRef = useRef(0);
  const silenceEndFrames = Math.max(
    1,
    Math.ceil(PCM_CONFIG.silenceEndMs / ((PCM_CONFIG.samplesPerChunk / PCM_CONFIG.sampleRate) * 1000))
  );

  const onAudioChunkRef = useRef(onAudioChunk);
  const onTurnEndRef = useRef(onTurnEnd);
  onAudioChunkRef.current = onAudioChunk;
  onTurnEndRef.current = onTurnEnd;

  // 转为 PCM + 能量检测
  const floatToBase64Pcm = useCallback((floatSamples: Float32Array): { base64: string; rms: number } => {
    const int16 = new Int16Array(floatSamples.length);
    let sumSq = 0;
    for (let i = 0; i < floatSamples.length; i++) {
      sumSq += floatSamples[i] * floatSamples[i];
      const s = Math.max(-1, Math.min(1, floatSamples[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const rms = Math.sqrt(sumSq / floatSamples.length);
    const bytes = new Uint8Array(int16.buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return { base64: btoa(binary), rms };
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setStatus("requesting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: PCM_CONFIG.channelCount,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate: PCM_CONFIG.sampleRate });
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioCtx.createScriptProcessor(PCM_CONFIG.samplesPerChunk, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        if (!recordingRef.current || mutedRef.current) return;

        const inputData = event.inputBuffer.getChannelData(0);
        const copy = new Float32Array(inputData.length);
        copy.set(inputData);
        const { base64, rms } = floatToBase64Pcm(copy);
        const isSpeech = rms >= PCM_CONFIG.rmsThreshold;

        let shouldSend = false;

        if (isSpeech) {
          speechActiveRef.current = true;
          silenceFramesRef.current = 0;
          shouldSend = true;
        } else if (speechActiveRef.current) {
          // 句末静音尾音也发送，便于后端 VAD 对齐
          silenceFramesRef.current += 1;
          shouldSend = true;
          if (silenceFramesRef.current >= silenceEndFrames) {
            speechActiveRef.current = false;
            silenceFramesRef.current = 0;
            onTurnEndRef.current?.();
          }
        }

        if (shouldSend) {
          sequenceRef.current += 1;
          onAudioChunkRef.current?.(base64, sequenceRef.current);
        }
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      recordingRef.current = true;
      speechActiveRef.current = false;
      silenceFramesRef.current = 0;
      setIsRecording(true);
      setStatus("active");
      console.log(`[Mic] Started (VAD silence=${PCM_CONFIG.silenceEndMs}ms)`);
    } catch (err) {
      const msg = String(err);
      if (msg.includes("Permission") || msg.includes("NotAllowed")) {
        setStatus("denied");
        setError("麦克风权限被拒绝，请允许浏览器访问麦克风，或使用文本输入模式");
      } else {
        setStatus("error");
        setError(`麦克风启动失败: ${msg}`);
      }
      onError?.(msg);
    }
  }, [floatToBase64Pcm, onError]);

  const stopRecording = useCallback(() => {
    recordingRef.current = false;
    speechActiveRef.current = false;
    silenceFramesRef.current = 0;
    setIsRecording(false);
    setStatus("idle");

    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    if (sourceRef.current) { sourceRef.current.disconnect(); sourceRef.current = null; }
    if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }

    sequenceRef.current = 0;
    console.log("[Mic] Stopped");
  }, []);

  useEffect(() => {
    return () => {
      recordingRef.current = false;
      if (processorRef.current) processorRef.current.disconnect();
      if (sourceRef.current) sourceRef.current.disconnect();
      if (audioCtxRef.current) audioCtxRef.current.close();
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { status, isRecording, startRecording, stopRecording, setMuted, error };
}
