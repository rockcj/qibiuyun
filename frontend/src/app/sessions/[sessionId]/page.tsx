"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import type { CreateSessionResponse } from "@/types/api";

/** 动态导入 VoiceSessionPanel（避免 SSR 时加载音频 API） */
const VoiceSessionPanel = dynamic(
  () => import("@/components/VoiceSessionPanel"),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">加载语音会话…</p>
        </div>
      </div>
    ),
  }
);

/** 实时对话页 — WebSocket 语音交互 */
export default function SessionPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<CreateSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 从 sessionStorage 恢复会话信息
    const raw = sessionStorage.getItem(`session:${sessionId}`);
    if (raw) {
      try {
        const data = JSON.parse(raw) as CreateSessionResponse;
        setSession(data);
      } catch {
        setError("无法解析会话信息，请返回首页重新创建");
      }
    } else {
      setError("未找到会话信息，请返回首页创建新会话");
    }
  }, [sessionId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-2xl dark:bg-red-900/30">
            ⚠️
          </div>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{error}</p>
          <a
            href="/"
            className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-500"
          >
            返回首页
          </a>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">加载会话…</p>
        </div>
      </div>
    );
  }

  return <VoiceSessionPanel session={session} />;
}
