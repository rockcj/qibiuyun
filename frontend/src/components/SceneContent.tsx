"use client";

import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import SceneConfigForm from "@/components/SceneConfigForm";
import type { SceneFull } from "@/types/api";

export default function SceneContent({ scene }: { scene: SceneFull }) {
  const { t } = useLocale();

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* 导航栏 */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-4xl items-center px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            {t("scene.backHome")}
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-extrabold text-zinc-900 dark:text-white">
          {scene.displayName}
        </h1>
        <p className="mt-2 text-zinc-500">{scene.description}</p>

        {/* 场景配置表单 */}
        <div className="mt-10">
          <SceneConfigForm scene={scene} />
        </div>
      </main>
    </div>
  );
}
