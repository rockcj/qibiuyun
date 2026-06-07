"use client";

import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import { useAuth } from "@/contexts/AuthContext";
import SceneCard, { type SceneCardData } from "@/components/SceneCard";

/** Hero 区域浮动光斑 */
function FloatingOrbs() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Indigo 光斑 - 左上 */}
      <div
        className="absolute h-72 w-72 rounded-full opacity-20"
        style={{
          background: "radial-gradient(circle, rgba(99,102,241,0.35) 0%, transparent 70%)",
          top: "-5%",
          left: "-8%",
          animation: "floatSlow 8s ease-in-out infinite",
        }}
      />
      {/* Amber 光斑 - 右上 */}
      <div
        className="absolute h-64 w-64 rounded-full opacity-15"
        style={{
          background: "radial-gradient(circle, rgba(245,158,11,0.3) 0%, transparent 70%)",
          top: "10%",
          right: "-5%",
          animation: "floatMedium 10s ease-in-out infinite",
        }}
      />
      {/* Emerald 光斑 - 中下 */}
      <div
        className="absolute h-56 w-56 rounded-full opacity-12"
        style={{
          background: "radial-gradient(circle, rgba(16,185,129,0.25) 0%, transparent 70%)",
          bottom: "-5%",
          left: "30%",
          animation: "floatFast 7s ease-in-out infinite",
        }}
      />
      {/* 小光斑 - indigo/purple */}
      <div
        className="absolute h-40 w-40 rounded-full opacity-10"
        style={{
          background: "radial-gradient(circle, rgba(139,92,246,0.3) 0%, transparent 70%)",
          bottom: "20%",
          right: "15%",
          animation: "floatSlow 9s ease-in-out infinite 2s",
        }}
      />
    </div>
  );
}

/** Hero 标签云 */
function HeroTags({ t }: { t: (key: string) => string }) {
  const tags = [
    { label: "🎯 AI 陪练", color: "#6366f1", bg: "#eef2ff" },
    { label: "⚡ 实时对话", color: "#d97706", bg: "#fef3c7" },
    { label: "📊 课后报告", color: "#059669", bg: "#ecfdf5" },
  ];

  return (
    <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
      {tags.map((tag, i) => (
        <span
          key={tag.label}
          className="inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold backdrop-blur-sm"
          style={{
            backgroundColor: tag.bg,
            color: tag.color,
            animation: `tagPopIn 0.4s ease-out ${0.3 + i * 0.1}s both`,
          }}
        >
          {tag.label}
        </span>
      ))}
    </div>
  );
}

export default function HomeContent({ scenes }: { scenes: SceneCardData[] }) {
  const { t } = useLocale();
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
      {/* ===== Header ===== */}
      <header className="relative border-b border-zinc-200/60 bg-white/70 backdrop-blur-xl">
        {/* 底部彩虹渐变条 */}
        <div
          className="absolute bottom-0 left-0 right-0 h-0.5"
          style={{
            background:
              "linear-gradient(90deg, #6366f1 0%, #a855f7 25%, #f59e0b 50%, #10b981 75%, #6366f1 100%)",
            backgroundSize: "200% 100%",
            animation: "gradientFlow 6s ease infinite",
          }}
        />

        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black tracking-tight text-zinc-900">
              Offer
              <span className="text-indigo-500">GPT</span>
            </span>
          </div>

          {/* 右侧导航 */}
          <nav className="flex items-center gap-4 text-sm text-zinc-500">
            <span className="hidden text-xs text-zinc-400 sm:inline">{t("header.subtitle")}</span>
            {isAuthenticated ? (
              <div className="flex items-center gap-3">
                <span className="text-sm text-zinc-700">
                  {t("auth.welcome")}，{user?.name || user?.email}
                </span>
                <button
                  onClick={() => {
                    logout();
                    window.location.href = "/";
                  }}
                  className="rounded-xl border border-zinc-200 bg-white px-4 py-2 text-xs font-medium text-zinc-600 transition-all duration-300 hover:border-zinc-300 hover:bg-zinc-50 hover:shadow-sm"
                >
                  {t("auth.logout")}
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                className="rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 px-5 py-2 text-xs font-semibold text-white shadow-md shadow-indigo-200 transition-all duration-300 hover:shadow-lg hover:shadow-indigo-300 hover:scale-105"
              >
                {t("auth.login.submit")}
              </Link>
            )}
          </nav>
        </div>
      </header>

      {/* ===== Hero ===== */}
      <section className="relative mx-auto w-full max-w-6xl px-6 pb-20 pt-24 text-center">
        {/* 浮动光斑背景 */}
        <FloatingOrbs />

        {/* 标签云 */}
        <HeroTags t={t} />

        {/* 主标题 */}
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight text-zinc-900 sm:text-5xl">
          {t("hero.title1")}{" "}
          <span className="bg-gradient-to-r from-indigo-500 via-amber-500 to-emerald-500 bg-clip-text text-transparent">
            {t("hero.title2")}
          </span>{" "}
          {t("hero.title3")}
        </h1>

        {/* 副标题 */}
        <p className="relative mx-auto mt-6 max-w-xl text-lg leading-relaxed text-zinc-500">
          {t("hero.subtitle")}
        </p>

        {/* ===== 场景卡片 ===== */}
        <div className="relative mt-16 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 justify-items-center">
          {scenes.map((scene, i) => (
            <SceneCard key={scene.scene} scene={scene} index={i} />
          ))}
        </div>
      </section>

      {/* ===== Footer ===== */}
      <footer
        className="mt-auto border-t py-8 text-center text-sm text-zinc-400"
        style={{
          borderImage: "linear-gradient(90deg, transparent, #6366f130, #f59e0b20, #10b98120, transparent) 1",
        }}
      >
        {t("footer.text")}
      </footer>
    </div>
  );
}
