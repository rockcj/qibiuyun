"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useLocale } from "@/i18n/LocaleContext";
import ResumeUploader from "@/components/ResumeUploader";
import JobDescriptionEditor from "@/components/JobDescriptionEditor";
import { createSession } from "@/lib/api";

function InterviewSetupContent() {
  const { t } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();

  // 从场景配置页传入的参数
  const topic = searchParams.get("topic") || "behavioral";
  const roleMode = searchParams.get("roleMode") || "founder";
  const personaMode = searchParams.get("personaMode") || roleMode;
  const difficultyLevel = searchParams.get("difficultyLevel") || "middle";
  const durationMinutes = Number(searchParams.get("durationMinutes") || "15");
  const realtimeLightCorrection = searchParams.get("realtimeLightCorrection") !== "false";

  const [resumeId, setResumeId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canStart = resumeId && jobId;

  const handleStartInterview = async () => {
    if (!resumeId || !jobId) return;

    setLoading(true);
    setError("");

    try {
      const session = await createSession({
        scene: "interview",
        topic,
        roleMode,
        personaMode,
        resumeId,
        jobId,
        durationMinutes,
        difficultyLevel,
        realtimeLightCorrection,
      });
      sessionStorage.setItem(`session:${session.sessionId}`, JSON.stringify(session));
      router.push(`/sessions/${session.sessionId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("config.error.generic"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-4xl items-center px-6">
          <Link
            href="/scenes/interview"
            className="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            {t("setup.backConfig")}
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-extrabold text-zinc-900 dark:text-white">
          {t("setup.title")}
        </h1>
        <p className="mt-2 text-zinc-500">{t("setup.subtitle")}</p>

        <div className="mt-10 space-y-8">
          <ResumeUploader
            onUploaded={(id) => setResumeId(id)}
          />
          <JobDescriptionEditor
            onCreated={(id) => setJobId(id)}
          />
        </div>

        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
            {error}
          </div>
        )}

        <div className="mt-10 flex items-center gap-4">
          <button
            type="button"
            onClick={handleStartInterview}
            disabled={!canStart || loading}
            className="rounded-xl bg-indigo-500 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition-all hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-50 dark:shadow-indigo-900/30"
          >
            {loading ? t("config.creating") : t("setup.startInterview")}
          </button>
          {!canStart && (
            <span className="text-xs text-zinc-400">{t("setup.needBoth")}</span>
          )}
        </div>
      </main>
    </div>
  );
}

export default function InterviewSetupPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading...</div>}>
      <InterviewSetupContent />
    </Suspense>
  );
}
