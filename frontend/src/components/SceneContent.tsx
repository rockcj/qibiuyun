"use client";

import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import SceneConfigForm from "@/components/SceneConfigForm";
import type { SceneFull } from "@/types/api";

/** 浮动光斑装饰 */
function FloatingOrbs() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute h-56 w-56 rounded-full opacity-15"
        style={{
          background: "radial-gradient(circle, rgba(99,102,241,0.3) 0%, transparent 70%)",
          top: "5%",
          right: "-6%",
          animation: "floatSlow 8s ease-in-out infinite",
        }}
      />
      <div
        className="absolute h-48 w-48 rounded-full opacity-10"
        style={{
          background: "radial-gradient(circle, rgba(245,158,11,0.25) 0%, transparent 70%)",
          bottom: "10%",
          left: "-5%",
          animation: "floatMedium 10s ease-in-out infinite 1s",
        }}
      />
    </div>
  );
}

export default function SceneContent({ scene }: { scene: SceneFull }) {
  const { t } = useLocale();

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
      {/* 浮动光斑 */}
      <FloatingOrbs />

      {/* Header */}
      <header className="relative border-b border-zinc-200/60 bg-white/70 backdrop-blur-xl">
        {/* 彩虹渐变底条 */}
        <div
          className="absolute bottom-0 left-0 right-0 h-0.5"
          style={{
            background:
              "linear-gradient(90deg, #6366f1 0%, #a855f7 25%, #f59e0b 50%, #10b981 75%, #6366f1 100%)",
            backgroundSize: "200% 100%",
            animation: "gradientFlow 6s ease infinite",
          }}
        />

        <div className="mx-auto flex h-16 max-w-4xl items-center px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-medium text-zinc-500 transition-colors hover:text-indigo-500"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            {t("scene.backHome")}
          </Link>
        </div>
      </header>

      {/* 主体 */}
      <main className="relative mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-extrabold tracking-tight text-zinc-900">
          {scene.displayName}
        </h1>
        <p className="mt-2 text-zinc-500">{scene.description}</p>

        {/* 评分维度预览标签 */}
        <div className="mt-4 flex flex-wrap gap-2">
          {scene.rubric.slice(0, 4).map((r) => (
            <span
              key={r}
              className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-500"
            >
              {r}
            </span>
          ))}
        </div>

        {/* 场景配置表单 */}
        <div className="mt-10">
          <SceneConfigForm scene={scene} />
        </div>
      </main>
    </div>
  );
}
