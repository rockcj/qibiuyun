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

/** 浮动光斑 */
function FloatingOrbs() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute h-64 w-64 rounded-full opacity-12"
        style={{ background: "radial-gradient(circle, rgba(99,102,241,0.3) 0%, transparent 70%)", top: "8%", right: "-5%", animation: "floatSlow 8s ease-in-out infinite" }} />
      <div className="absolute h-48 w-48 rounded-full opacity-10"
        style={{ background: "radial-gradient(circle, rgba(245,158,11,0.25) 0%, transparent 70%)", bottom: "15%", left: "-4%", animation: "floatMedium 10s ease-in-out infinite 1s" }} />
    </div>
  );
}

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
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
      <FloatingOrbs />

      {/* Header */}
      <header className="relative border-b border-zinc-200/60 bg-white/70 backdrop-blur-xl">
        <div className="absolute bottom-0 left-0 right-0 h-0.5"
          style={{ background: "linear-gradient(90deg, #6366f1 0%, #a855f7 25%, #f59e0b 50%, #10b981 75%, #6366f1 100%)", backgroundSize: "200% 100%", animation: "gradientFlow 6s ease infinite" }} />

        <div className="mx-auto flex h-16 max-w-6xl items-center px-6">
          <Link href="/scenes/interview"
            className="flex items-center gap-2 text-sm font-medium text-zinc-500 transition-colors hover:text-indigo-500">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            {t("setup.backConfig")}
          </Link>
        </div>
      </header>

      {/* 主体 */}
      <main className="relative mx-auto w-full max-w-6xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-extrabold tracking-tight text-zinc-900">{t("setup.title")}</h1>
        <p className="mt-2 text-zinc-500">{t("setup.subtitle")}</p>

        <div className="mt-10 space-y-8">
          {/* 简历 + JD 左右两列并排 */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ResumeUploader onUploaded={(id) => setResumeId(id)} />
            <JobDescriptionEditor onCreated={(id) => setJobId(id)} />
          </div>

          {/* ASR 模型选择 — 全宽 */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <span className="text-lg">🎤</span>
              <span className="font-bold text-zinc-800">语音识别模型</span>
              <span className="ml-auto text-xs text-zinc-400">影响识别准确率和响应速度</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {ASR_MODELS.map((m) => {
                const isSelected = asrModel === m.key;
                const isThisSwitching = isSelected && modelSwitching;
                return (
                  <button key={m.key} type="button"
                    onClick={() => handleModelSwitch(m.key)}
                    disabled={modelSwitching}
                    className={`relative rounded-xl p-4 text-center transition-all duration-300 ${
                      isSelected
                        ? "border-2 border-indigo-400 bg-gradient-to-br from-indigo-50 to-purple-50 shadow-md shadow-indigo-100"
                        : "border-2 border-zinc-100 bg-zinc-50 hover:border-zinc-300 hover:bg-white hover:shadow-sm"
                    } ${modelSwitching && !isSelected ? "cursor-not-allowed opacity-40" : ""}`}>
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
                    <div className="mt-1.5 text-sm font-bold text-zinc-800">{m.label}</div>
                    <div className="text-xs text-zinc-500">{m.desc}</div>
                    <div className="text-[11px] text-zinc-400">{m.accuracy}</div>
                    <div className="mt-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-500">{m.tag}</div>
                  </button>
                );
              })}
            </div>
            {modelSwitching && (
              <p className="mt-3 flex items-center gap-2 text-xs font-medium text-indigo-500">
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
                正在加载 {ASR_MODELS.find((m) => m.key === asrModel)?.label} 模型，请稍候...
              </p>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm font-medium text-red-600">{error}</div>
        )}

        <div className="mt-10 flex items-center gap-4">
          <button type="button" onClick={handleStartInterview}
            disabled={!canStart || loading}
            className="rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 px-8 py-3.5 text-sm font-bold text-white shadow-lg shadow-indigo-200 transition-all duration-300 hover:shadow-xl hover:shadow-indigo-300 hover:scale-[1.03] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100">
            {loading
              ? t("config.creating")
              : modelSwitching
                ? "模型加载中..."
                : `${t("setup.startInterview")} (${ASR_MODELS.find((m) => m.key === asrModel)?.label || asrModel})`}
          </button>
          {!canStart && !modelSwitching && (
            <span className="text-xs text-zinc-400">{t("setup.needBoth")}</span>
          )}
          {!modelReady && (
            <span className="text-xs font-medium text-indigo-500 animate-pulse">模型切换中，请稍候...</span>
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
