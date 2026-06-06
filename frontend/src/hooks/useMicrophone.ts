/** 麦克风 Hook – PCM 采集 + 静音控制 + 能量过滤 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const PCM_CONFIG = {
  sampleRate: 16000,
  channelCount: 1,
  samplesPerChunk: 1024, // 64ms @ 16kHz
  /** RMS 能量阈值：低于此值的帧视为静音，不发送（-42dB ≈ 0.008，防背景噪音） */
  rmsThreshold: 0.008,
};

export type MicStatus = "idle" | "requesting" | "active" | "error" | "denied";

interface UseMicrophoneOptions {
  onAudioChunk?: (base64Pcm: string, sequenceId: number) => void;
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
  const { onAudioChunk, onError } = options;

  const [status, setStatus] = useState<MicStatus>("idle");
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const sequenceRef = useRef(0);
  const recordingRef = useRef(false);

  // 静音控制：设为 true 时停止发送音频（TTS 播放期间使用）
  const mutedRef = useRef(false);
  const setMuted = useCallback((muted: boolean) => {
    mutedRef.current = muted;
    if (muted) {
      console.log("[Mic] Muted (TTS playing)");
    } else {
      console.log("[Mic] Unmuted");
    }
  }, []);

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
        // 停止录音 → 不发
        if (!recordingRef.current) return;
        // TTS 播放中（静音）→ 不发
        if (mutedRef.current) return;

        const inputData = event.inputBuffer.getChannelData(0);
        const copy = new Float32Array(inputData.length);
        copy.set(inputData);

        // 能量过滤：RMS 低于阈值 → 静音噪音 → 不发
        const { base64, rms } = floatToBase64Pcm(copy);
        if (rms < PCM_CONFIG.rmsThreshold) return;

        sequenceRef.current += 1;
        onAudioChunk?.(base64, sequenceRef.current);
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      recordingRef.current = true;
      setIsRecording(true);
      setStatus("active");
      console.log(`[Mic] Started (16kHz, threshold=${PCM_CONFIG.rmsThreshold})`);
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
  }, [floatToBase64Pcm, onAudioChunk, onError]);

  const stopRecording = useCallback(() => {
    recordingRef.current = false;
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
