"use client";

import { useLocale } from "@/i18n/LocaleContext";
import SceneCard, { type SceneCardData } from "@/components/SceneCard";

export default function HomeContent({ scenes }: { scenes: SceneCardData[] }) {
  const { t } = useLocale();

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-zinc-50 to-white dark:from-zinc-950 dark:to-black">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black tracking-tight text-zinc-900 dark:text-white">
              Offer<span className="text-indigo-500">GPT</span>
            </span>
          </div>
          <nav className="flex items-center gap-4 text-sm text-zinc-500">
            <span className="hidden sm:inline">{t("header.subtitle")}</span>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto w-full max-w-6xl px-6 pb-16 pt-20 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight text-zinc-900 sm:text-5xl dark:text-white">
          {t("hero.title1")}{" "}
          <span className="bg-gradient-to-r from-indigo-500 via-amber-500 to-emerald-500 bg-clip-text text-transparent">
            {t("hero.title2")}
          </span>{" "}
          {t("hero.title3")}
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-zinc-500 dark:text-zinc-400">
          {t("hero.subtitle")}
        </p>

        {/* Scene cards */}
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 justify-items-center">
          {scenes.map((scene, i) => (
            <SceneCard key={scene.scene} scene={scene} index={i} />
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-zinc-200 py-8 text-center text-sm text-zinc-400 dark:border-zinc-800">
        {t("footer.text")}
      </footer>
    </div>
  );
}
