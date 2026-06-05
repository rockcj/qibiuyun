"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale } from "@/i18n/LocaleContext";
import type { CreateSessionResponse } from "@/types/api";

/** 实时对话页占位 – Step 3 将实现完整语音链路 */
export default function SessionPage() {
  const { t } = useLocale();
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<CreateSessionResponse | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem(`session:${sessionId}`);
    if (raw) {
      try {
        setSession(JSON.parse(raw));
      } catch {
        /* 忽略解析错误 */
      }
    }
  }, [sessionId]);

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6">
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
          >
            {t("scene.backHome")}
          </Link>
          <span className="text-xs text-zinc-400">
            {t("session.id")}: {sessionId.slice(0, 8)}…
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 text-center">
        <div className="mx-auto max-w-lg rounded-2xl border border-zinc-200 bg-white p-10 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 text-2xl dark:bg-indigo-900/30">
            🎙️
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">
            {t("session.created")}
          </h1>
          <p className="mt-3 text-sm text-zinc-500">{t("session.placeholder")}</p>

          {session && (
            <div className="mt-6 space-y-2 text-left text-sm text-zinc-600 dark:text-zinc-400">
              <p>
                <span className="font-medium">{t("session.scene")}:</span> {session.scene}
              </p>
              <p>
                <span className="font-medium">{t("session.topic")}:</span> {session.topic}
              </p>
              {session.persona && (
                <p>
                  <span className="font-medium">{t("session.persona")}:</span>{" "}
                  {session.persona.displayName}
                </p>
              )}
              <p className="break-all text-xs text-zinc-400">
                WebSocket: {session.websocketUrl}
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
