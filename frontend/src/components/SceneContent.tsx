"use client";

import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";

interface SceneFull {
  scene: string;
  displayName: string;
  description: string;
  topics: { topic: string; displayName: string }[];
  roleModes: { roleMode: string; displayName: string }[];
  rubric: string[];
  requiresResumeJD: boolean;
}

export default function SceneContent({ scene }: { scene: SceneFull }) {
  const { t } = useLocale();

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* Nav */}
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

        {/* Topics */}
        <section className="mt-10">
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            {t("scene.topics")}
          </h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {scene.topics.map((t) => (
              <div
                key={t.topic}
                className="rounded-xl border border-zinc-200 bg-white p-4 text-sm font-medium text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
              >
                {t.displayName}
              </div>
            ))}
          </div>
        </section>

        {/* Roles */}
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            {t("scene.roles")}
          </h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {scene.roleModes.map((r) => (
              <div
                key={r.roleMode}
                className="rounded-xl border border-zinc-200 bg-white p-4 text-sm font-medium text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
              >
                {r.displayName}
              </div>
            ))}
          </div>
        </section>

        {/* Rubric */}
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            {t("scene.rubric")}
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {scene.rubric.map((r) => (
              <span
                key={r}
                className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-300"
              >
                {r}
              </span>
            ))}
          </div>
        </section>

        {/* CTA */}
        <div className="mt-12 flex items-center gap-4">
          <button className="rounded-xl bg-indigo-500 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition-all hover:bg-indigo-600 dark:shadow-indigo-900/30">
            {t("scene.startTraining")}
          </button>
          {scene.requiresResumeJD && (
            <span className="text-xs text-zinc-400">{t("scene.requiresResume")}</span>
          )}
        </div>
      </main>
    </div>
  );
}
