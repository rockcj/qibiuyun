"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useLocale } from "@/i18n/LocaleContext";
import ResumeUploader from "@/components/ResumeUploader";
import JobDescriptionEditor from "@/components/JobDescriptionEditor";
import { createSession, switchAsrModel, getAsrStatus } from "@/lib/api";

/** ASR 模型选项 */
const ASR_MODELS = [
  { key: "mini", label: "Mini", icon: "⚡", desc: "快速响应", accuracy: "~78%", tag: "适合测试" },
  { key: "max", label: "Max", icon: "🎯", desc: "均衡推荐", accuracy: "~85%", tag: "日常使用" },
  { key: "max-pro", label: "Max Pro", icon: "🔬", desc: "精准识别", accuracy: "~91%", tag: "高配置" },
];

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

  // ASR 模型选择
  const [asrModel, setAsrModel] = useState("max");
  const [modelReady, setModelReady] = useState(true);
  const [modelSwitching, setModelSwitching] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 初始化时查询当前模型状态
  useEffect(() => {
    getAsrStatus().then((s) => {
      setAsrModel(s.model);
      setModelReady(s.ready);
    }).catch(() => {});
  }, []);

  // 切换模型
  const handleModelSwitch = useCallback(async (model: string) => {
    if (model === asrModel || modelSwitching) return;
    setAsrModel(model);
    setModelReady(false);
    setModelSwitching(true);

    try {
      await switchAsrModel(model);
      // 轮询直到模型就绪
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const s = await getAsrStatus();
          if (s.ready) {
            setModelReady(true);
            setModelSwitching(false);
            if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          }
        } catch { /* 继续轮询 */ }
      }, 800);
    } catch {
      setModelSwitching(false);
    }
  }, [asrModel, modelSwitching]);

  // 清理轮询
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const canStart = resumeId && jobId && modelReady;

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

          {/* ASR 模型选择 */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-lg">🎤</span>
              <span className="font-semibold text-zinc-800 dark:text-zinc-200">语音识别模型</span>
              <span className="ml-auto text-[11px] text-zinc-400">影响识别准确率和响应速度</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {ASR_MODELS.map((m) => {
                const isSelected = asrModel === m.key;
                const isThisSwitching = isSelected && modelSwitching;
                return (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => handleModelSwitch(m.key)}
                    disabled={modelSwitching}
                    className={`relative rounded-xl p-3.5 text-center transition-all duration-300 ${
                      isSelected
                        ? "border-2 border-indigo-500 bg-indigo-50 shadow-sm dark:border-indigo-400 dark:bg-indigo-950/40"
                        : "border-2 border-zinc-100 bg-zinc-50 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-800/50 dark:hover:border-zinc-600"
                    } ${modelSwitching && !isSelected ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    {isSelected && (
                      <div className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500">
                        {isThisSwitching ? (
                          <div className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        ) : (
                          <span className="text-[10px] text-white">✓</span>
                        )}
                      </div>
                    )}
                    <div className="text-2xl">{m.icon}</div>
                    <div className="mt-1.5 text-sm font-bold text-zinc-800 dark:text-zinc-200">{m.label}</div>
                    <div className="text-[11px] text-zinc-500 dark:text-zinc-400">{m.desc}</div>
                    <div className="mt-0.5 text-[10px] text-zinc-400">{m.accuracy}</div>
                    <div className="mt-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">{m.tag}</div>
                  </button>
                );
              })}
            </div>
            {modelSwitching && (
              <p className="mt-3 flex items-center gap-2 text-center text-xs text-indigo-600 dark:text-indigo-400">
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
                正在加载 {ASR_MODELS.find((m) => m.key === asrModel)?.label} 模型，请稍候...
              </p>
            )}
          </div>
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
            {loading
              ? t("config.creating")
              : modelSwitching
                ? "模型加载中..."
                : `${t("setup.startInterview")} (${ASR_MODELS.find((m) => m.key === asrModel)?.label || asrModel})`
            }
          </button>
          {!canStart && !modelSwitching && (
            <span className="text-xs text-zinc-400">{t("setup.needBoth")}</span>
          )}
          {!modelReady && (
            <span className="text-xs text-indigo-500 animate-pulse">模型切换中，请稍候...</span>
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
