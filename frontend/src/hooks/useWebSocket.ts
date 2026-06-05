/** WebSocket Hook – 连接管理、自动重连、消息路由 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WsServerMessage } from "@/types/api";

/** WebSocket 连接状态枚举 — 与 UI 提示文案一一对应 */
export type ConnectionStatus =
  | "disconnected"   // 未连接
  | "connecting"     // 正在建立 WebSocket 连接
  | "connected"      // WebSocket 已连接，等待麦克风就绪
  | "mic_ready"      // 麦克风就绪，可以开始对话
  | "error";         // 连接失败（WebSocket 错误或麦克风拒绝）

interface UseWebSocketOptions {
  url: string;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnects?: number;
  onMessage?: (msg: WsServerMessage) => void;
}

interface UseWebSocketReturn {
  status: ConnectionStatus;
  sendMessage: (msg: Record<string, unknown>) => void;
  connect: () => void;
  disconnect: () => void;
  error: string | null;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnects = 3,
    onMessage,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  // 防 StrictMode 双重调用：正在连接中时跳过第二次 connect()
  const connectingRef = useRef(false);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    connectingRef.current = false;
    clearReconnectTimer();
    reconnectCount.current = 0;
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    if (wsRef.current) {
      // 设为 1000(normal) 防止触发 reconnect
      wsRef.current.close(1000);
      wsRef.current = null;
    }
    if (mountedRef.current) {
      setStatus("disconnected");
    }
  }, [clearReconnectTimer]);

  const connect = useCallback(() => {
    if (!url) return;
    // 已在连接中或已连接 → 跳过
    if (connectingRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

    connectingRef.current = true;

    // 清理旧连接
    if (wsRef.current) {
      wsRef.current.close(1000);
      wsRef.current = null;
    }

    if (mountedRef.current) {
      setStatus("connecting");
      setError(null);
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        connectingRef.current = false;
        if (!mountedRef.current) return;
        setStatus("connected");
        reconnectCount.current = 0;
        console.log("[WS] Connected");

        // 心跳
        if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
        heartbeatTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const msg = JSON.parse(event.data as string) as WsServerMessage;
          onMessage?.(msg);
        } catch {
          console.warn("[WS] Parse error");
        }
      };

      ws.onerror = () => {
        connectingRef.current = false;
        if (!mountedRef.current) return;
        setStatus("error");
        setError("WebSocket 连接错误");
      };

      ws.onclose = (event) => {
        connectingRef.current = false;
        if (heartbeatTimer.current) { clearInterval(heartbeatTimer.current); heartbeatTimer.current = null; }
        if (!mountedRef.current) return;
        setStatus("disconnected");

        // 非正常关闭 → 自动重连
        if (event.code !== 1000 && reconnectCount.current < maxReconnects) {
          reconnectCount.current += 1;
          reconnectTimer.current = setTimeout(() => {
            if (mountedRef.current) connect();
          }, reconnectInterval);
        }
      };
    } catch (err) {
      connectingRef.current = false;
      if (mountedRef.current) {
        setError(`WebSocket 创建失败: ${String(err)}`);
        setStatus("disconnected");
      }
    }
  }, [url, reconnectInterval, maxReconnects, onMessage]);

  const sendMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(msg));
      }
    },
    []
  );

  useEffect(() => {
    mountedRef.current = true;
    connectingRef.current = false;
    if (autoConnect && url) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      connectingRef.current = false;
      clearReconnectTimer();
      if (heartbeatTimer.current) { clearInterval(heartbeatTimer.current); heartbeatTimer.current = null; }
      if (wsRef.current) {
        wsRef.current.close(1000);
        wsRef.current = null;
      }
    };
  }, [url, autoConnect]);  // 去掉了 connect, clearReconnectTimer 依赖，避免每次 render 重建

  return { status, sendMessage, connect, disconnect, error };
}
