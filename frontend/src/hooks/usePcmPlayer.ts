/** PCM 播放器 Hook – 播放云端语音下发的 pcm16 音频流（WebAudio 直通调度） */

"use client";

import { useCallback, useEffect, useRef } from "react";

interface UsePcmPlayerOptions {
  /** 音频采样率，云端默认 24000 */
  sampleRate?: number;
  onStart?: () => void;
  onEnd?: () => void;
}

interface UsePcmPlayerReturn {
  /** 追加一段 base64 pcm16 音频（按到达顺序无缝衔接播放） */
  push: (base64Pcm: string) => void;
  /** 立即停止并清空播放队列 */
  clear: () => void;
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export function usePcmPlayer(options: UsePcmPlayerOptions = {}): UsePcmPlayerReturn {
  const { sampleRate = 24000, onStart, onEnd } = options;

  const ctxRef = useRef<AudioContext | null>(null);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const nextTimeRef = useRef(0);
  const activeRef = useRef(0);
  const startedRef = useRef(false);

  const onStartRef = useRef(onStart);
  const onEndRef = useRef(onEnd);
  onStartRef.current = onStart;
  onEndRef.current = onEnd;

  const ensureContext = useCallback((): AudioContext | null => {
    if (typeof window === "undefined") return null;
    if (!ctxRef.current) {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) {
        console.warn("[PCM] 浏览器不支持 WebAudio，无法播放云端语音");
        return null;
      }
      ctxRef.current = new Ctor();
    }
    if (ctxRef.current.state === "suspended") {
      ctxRef.current.resume().catch(() => {});
    }
    return ctxRef.current;
  }, []);

  const push = useCallback(
    (base64Pcm: string) => {
      if (!base64Pcm) return;
      const ctx = ensureContext();
      if (!ctx) return;

      let bytes: Uint8Array;
      try {
        bytes = base64ToBytes(base64Pcm);
      } catch {
        console.warn("[PCM] base64 解码失败");
        return;
      }
      const sampleCount = Math.floor(bytes.length / 2);
      if (sampleCount <= 0) return;

      const buffer = ctx.createBuffer(1, sampleCount, sampleRate);
      const channel = buffer.getChannelData(0);
      const view = new DataView(bytes.buffer, bytes.byteOffset, sampleCount * 2);
      for (let i = 0; i < sampleCount; i++) {
        channel[i] = view.getInt16(i * 2, true) / 32768;
      }

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);

      // 串行调度：首包留 20ms 缓冲，后续紧接上一包结束时间
      const startAt = Math.max(ctx.currentTime + 0.02, nextTimeRef.current);
      source.start(startAt);
      nextTimeRef.current = startAt + buffer.duration;

      sourcesRef.current.add(source);
      activeRef.current += 1;
      if (!startedRef.current) {
        startedRef.current = true;
        onStartRef.current?.();
      }

      source.onended = () => {
        sourcesRef.current.delete(source);
        activeRef.current -= 1;
        if (activeRef.current <= 0) {
          activeRef.current = 0;
          nextTimeRef.current = 0;
          if (startedRef.current) {
            startedRef.current = false;
            onEndRef.current?.();
          }
        }
      };
    },
    [ensureContext, sampleRate]
  );

  const clear = useCallback(() => {
    sourcesRef.current.forEach((source) => {
      try {
        source.onended = null;
        source.stop();
      } catch {
        // 已结束的音源调用 stop 会抛错，忽略
      }
    });
    sourcesRef.current.clear();
    activeRef.current = 0;
    nextTimeRef.current = 0;
    const wasStarted = startedRef.current;
    startedRef.current = false;
    if (wasStarted) onEndRef.current?.();
  }, []);

  useEffect(() => {
    return () => {
      sourcesRef.current.forEach((source) => {
        try {
          source.onended = null;
          source.stop();
        } catch {
          // ignore
        }
      });
      sourcesRef.current.clear();
      if (ctxRef.current) {
        ctxRef.current.close().catch(() => {});
        ctxRef.current = null;
      }
    };
  }, []);

  return { push, clear };
}
