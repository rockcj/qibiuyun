/** 麦克风 Hook – AudioContext + AudioWorklet 采集 PCM，通过 WebSocket 发送 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** 标准 PCM 格式：16kHz, mono, 16-bit */
const PCM_CONFIG = {
  sampleRate: 16000,
  channelCount: 1,
  // ScriptProcessor bufferSize 必须是 2 的幂
  // 1024 采样点 ≈ 64ms/片 @ 16kHz
  chunkMs: 64,
  samplesPerChunk: 1024,
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
  const sourceRef = useRef<MediaStreamSourceNode | null>(null);
  const sequenceRef = useRef(0);
  // 用 ref 避免 onaudioprocess 闭包拿到陈旧值
  const recordingRef = useRef(false);

  // 将 Float32Array 转为 16-bit PCM 的 base64
  const floatToBase64Pcm = useCallback((floatSamples: Float32Array): string => {
    const int16 = new Int16Array(floatSamples.length);
    for (let i = 0; i < floatSamples.length; i++) {
      const s = Math.max(-1, Math.min(1, floatSamples[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const bytes = new Uint8Array(int16.buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }, []);

  // 开始录音
  const startRecording = useCallback(async () => {
    setError(null);
    setStatus("requesting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: PCM_CONFIG.sampleRate,
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

      // bufferSize 必须是 2 的幂，1024 = 64ms/片
      const processor = audioCtx.createScriptProcessor(PCM_CONFIG.samplesPerChunk, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        // 用 ref 而非 state，避免闭包陈旧值
        if (!recordingRef.current) return;
        const inputData = event.inputBuffer.getChannelData(0);
        const copy = new Float32Array(inputData.length);
        copy.set(inputData);

        const base64Pcm = floatToBase64Pcm(copy);
        sequenceRef.current += 1;
        onAudioChunk?.(base64Pcm, sequenceRef.current);
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      recordingRef.current = true;
      setIsRecording(true);
      setStatus("active");
      console.log("[Mic] Recording started, 16kHz mono PCM, buffer=1024");
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

  // 停止录音
  const stopRecording = useCallback(() => {
    recordingRef.current = false;
    setIsRecording(false);
    setStatus("idle");

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    sequenceRef.current = 0;
    console.log("[Mic] Recording stopped");
  }, []);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      recordingRef.current = false;
      if (processorRef.current) processorRef.current.disconnect();
      if (sourceRef.current) sourceRef.current.disconnect();
      if (audioCtxRef.current) audioCtxRef.current.close();
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { status, isRecording, startRecording, stopRecording, error };
}
