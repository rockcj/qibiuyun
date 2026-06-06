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

/** React Strict Mode 下延迟建连，避免 mount/unmount 连续触发 accept→close 风暴 */
const STRICT_MODE_CONNECT_DELAY_MS = 80;

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
  const connectDelayTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const connectingRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
  }, []);

  const clearConnectDelayTimer = useCallback(() => {
    if (connectDelayTimer.current) {
      clearTimeout(connectDelayTimer.current);
      connectDelayTimer.current = null;
    }
  }, []);

  const teardownWebSocket = useCallback((ws: WebSocket | null) => {
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close(1000);
    }
  }, []);

  const disconnect = useCallback(() => {
    connectingRef.current = false;
    clearReconnectTimer();
    clearConnectDelayTimer();
    reconnectCount.current = 0;
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    teardownWebSocket(wsRef.current);
    wsRef.current = null;
    if (mountedRef.current) {
      setStatus("disconnected");
    }
  }, [clearReconnectTimer, clearConnectDelayTimer, teardownWebSocket]);

  const connect = useCallback(() => {
    if (!url || !mountedRef.current) return;
    if (connectingRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    connectingRef.current = true;
    teardownWebSocket(wsRef.current);
    wsRef.current = null;

    if (mountedRef.current) {
      setStatus("connecting");
      setError(null);
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        connectingRef.current = false;
        if (!mountedRef.current || wsRef.current !== ws) return;
        setStatus("connected");
        reconnectCount.current = 0;
        console.log("[WS] Connected");

        if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
        heartbeatTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current || wsRef.current !== ws) return;
        try {
          const msg = JSON.parse(event.data as string) as WsServerMessage;
          onMessageRef.current?.(msg);
        } catch {
          console.warn("[WS] Parse error");
        }
      };

      ws.onerror = () => {
        connectingRef.current = false;
        if (!mountedRef.current || wsRef.current !== ws) return;
        setStatus("error");
        setError("WebSocket 连接错误");
      };

      ws.onclose = (event) => {
        connectingRef.current = false;
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
          heartbeatTimer.current = null;
        }
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (!mountedRef.current || wsRef.current !== null) return;
        setStatus("disconnected");

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
  }, [url, reconnectInterval, maxReconnects, teardownWebSocket]);

  const scheduleConnect = useCallback(() => {
    clearConnectDelayTimer();
    connectDelayTimer.current = setTimeout(() => {
      connectDelayTimer.current = null;
      if (mountedRef.current) {
        connect();
      }
    }, STRICT_MODE_CONNECT_DELAY_MS);
  }, [clearConnectDelayTimer, connect]);

  const sendMessage = useCallback(
    (msg: Record<string, unknown>) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
        return true;
      }
      return false;
    },
    []
  );

  useEffect(() => {
    mountedRef.current = true;
    connectingRef.current = false;
    if (autoConnect && url) {
      scheduleConnect();
    }
    return () => {
      mountedRef.current = false;
      connectingRef.current = false;
      clearReconnectTimer();
      clearConnectDelayTimer();
      if (heartbeatTimer.current) {
        clearInterval(heartbeatTimer.current);
        heartbeatTimer.current = null;
      }
      teardownWebSocket(wsRef.current);
      wsRef.current = null;
    };
  }, [url, autoConnect, scheduleConnect, clearReconnectTimer, clearConnectDelayTimer, teardownWebSocket]);

  return { status, sendMessage, connect, disconnect, error };
}
