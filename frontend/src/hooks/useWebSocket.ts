/** WebSocket Hook – 连接管理、自动重连、消息路由 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WsServerMessage } from "@/types/api";

export type ConnectionStatus = "disconnected" | "connecting" | "connected";

interface UseWebSocketOptions {
  /** WebSocket 地址 */
  url: string;
  /** 是否自动连接 */
  autoConnect?: boolean;
  /** 重连间隔 ms */
  reconnectInterval?: number;
  /** 最大重连次数 */
  maxReconnects?: number;
  /** 收到消息回调 */
  onMessage?: (msg: WsServerMessage) => void;
}

interface UseWebSocketReturn {
  /** 连接状态 */
  status: ConnectionStatus;
  /** 发送 JSON 消息 */
  sendMessage: (msg: Record<string, unknown>) => void;
  /** 手动连接 */
  connect: () => void;
  /** 手动断开 */
  disconnect: () => void;
  /** 错误信息 */
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
  const mountedRef = useRef(true);

  // 清理定时器
  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
  }, []);

  // 断开连接
  const disconnect = useCallback(() => {
    clearReconnectTimer();
    reconnectCount.current = 0;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mountedRef.current) {
      setStatus("disconnected");
    }
  }, [clearReconnectTimer]);

  // 连接
  const connect = useCallback(() => {
    if (!url) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // 清理旧连接
    if (wsRef.current) {
      wsRef.current.close();
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
        if (!mountedRef.current) return;
        setStatus("connected");
        reconnectCount.current = 0;
        console.log("[WS] Connected:", url);

        // 连接后发送心跳
        const heartbeat = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          } else {
            clearInterval(heartbeat);
          }
        }, 15000);

        ws.addEventListener("close", () => clearInterval(heartbeat), { once: true });
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const msg = JSON.parse(event.data as string) as WsServerMessage;
          onMessage?.(msg);
        } catch {
          console.warn("[WS] Failed to parse message:", event.data);
        }
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        setError("WebSocket 连接错误");
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setStatus("disconnected");
        console.log("[WS] Disconnected:", event.code, event.reason);

        // 自动重连
        if (reconnectCount.current < maxReconnects && event.code !== 1000) {
          reconnectCount.current += 1;
          console.log(
            `[WS] Reconnecting ${reconnectCount.current}/${maxReconnects} in ${reconnectInterval}ms...`
          );
          reconnectTimer.current = setTimeout(() => {
            if (mountedRef.current) {
              connect();
            }
          }, reconnectInterval);
        }
      };
    } catch (err) {
      if (mountedRef.current) {
        setError(`WebSocket 创建失败: ${String(err)}`);
        setStatus("disconnected");
      }
    }
  }, [url, reconnectInterval, maxReconnects, onMessage]);

  // 发送消息
  const sendMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(msg));
      } else {
        console.warn("[WS] Cannot send, not connected");
      }
    },
    []
  );

  // 自动连接
  useEffect(() => {
    mountedRef.current = true;
    if (autoConnect && url) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url, autoConnect, connect, clearReconnectTimer]);

  return { status, sendMessage, connect, disconnect, error };
}
