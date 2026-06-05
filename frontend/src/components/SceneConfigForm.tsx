"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";
import { createSession } from "@/lib/api";
import type { SceneConfigState, SceneFull } from "@/types/api";

interface SceneConfigFormProps {
  scene: SceneFull;
}

const DIFFICULTY_OPTIONS = [
  { value: "junior", labelKey: "config.difficulty.junior" as const },
  { value: "middle", labelKey: "config.difficulty.middle" as const },
  { value: "senior", labelKey: "config.difficulty.senior" as const },
];

const DURATION_OPTIONS = [8, 15, 20, 30];

export default function SceneConfigForm({ scene }: SceneConfigFormProps) {
  const { t } = useLocale();
  const router = useRouter();

  const [config, setConfig] = useState<SceneConfigState>({
    topic: scene.topics[0]?.topic || "",
    roleMode: scene.roleModes[0]?.roleMode || "",
    difficultyLevel: "middle",
    durationMinutes: 15,
    realtimeLightCorrection: true,
    personaMode: scene.roleModes[0]?.roleMode || "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isInterview = scene.scene === "interview";

  /** 面试场景：跳转到资料配置页 */
  const handleInterviewNext = () => {
    const params = new URLSearchParams({
      topic: config.topic,
      roleMode: config.roleMode,
      personaMode: config.personaMode,
      difficultyLevel: config.difficultyLevel,
      durationMinutes: String(config.durationMinutes),
      realtimeLightCorrection: String(config.realtimeLightCorrection),
    });
    router.push(`/interview/setup?${params.toString()}`);
  };

  /** 点餐/会议场景：直接创建会话（不绑定简历/JD） */
  const handleDirectCreate = async () => {
    setLoading(true);
    setError("");
    try {
      const session = await createSession({
        scene: scene.scene,
        topic: config.topic,
        roleMode: config.roleMode,
        personaMode: config.personaMode,
        durationMinutes: config.durationMinutes,
        difficultyLevel: config.difficultyLevel,
        realtimeLightCorrection: config.realtimeLightCorrection,
      });
      // 保存会话令牌供实时页使用
      sessionStorage.setItem(`session:${session.sessionId}`, JSON.stringify(session));
      router.push(`/sessions/${session.sessionId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("config.error.generic"));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (isInterview) {
      handleInterviewNext();
    } else {
      handleDirectCreate();
    }
  };

  return (
    <div className="space-y-8">
      {/* 子主题选择 */}
      <section>
        <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
          {t("scene.topics")}
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {scene.topics.map((topic) => (
            <button
              key={topic.topic}
              type="button"
              onClick={() => setConfig((c) => ({ ...c, topic: topic.topic }))}
              className={`rounded-xl border p-4 text-sm font-medium transition-all ${
                config.topic === topic.topic
                  ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-300"
                  : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
              }`}
            >
              {topic.displayName}
            </button>
          ))}
        </div>
      </section>

      {/* AI 角色选择 */}
      <section>
        <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
          {t("scene.roles")}
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {scene.roleModes.map((role) => (
            <button
              key={role.roleMode}
              type="button"
              onClick={() =>
                setConfig((c) => ({
                  ...c,
                  roleMode: role.roleMode,
                  personaMode: role.roleMode,
                }))
              }
              className={`rounded-xl border p-4 text-left text-sm font-medium transition-all ${
                config.roleMode === role.roleMode
                  ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-300"
                  : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
              }`}
            >
              {role.displayName}
            </button>
          ))}
        </div>
      </section>

      {/* 难度与时长 */}
      <section className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div>
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            {t("config.difficulty")}
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {DIFFICULTY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setConfig((c) => ({ ...c, difficultyLevel: opt.value }))}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                  config.difficultyLevel === opt.value
                    ? "bg-indigo-500 text-white"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
                }`}
              >
                {t(opt.labelKey)}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            {t("config.duration")}
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {DURATION_OPTIONS.map((min) => (
              <button
                key={min}
                type="button"
                onClick={() => setConfig((c) => ({ ...c, durationMinutes: min }))}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                  config.durationMinutes === min
                    ? "bg-indigo-500 text-white"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
                }`}
              >
                {min} {t("config.minutes")}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* 实时轻纠正开关 */}
      <section>
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={config.realtimeLightCorrection}
            onChange={(e) =>
              setConfig((c) => ({ ...c, realtimeLightCorrection: e.target.checked }))
            }
            className="h-5 w-5 rounded border-zinc-300 text-indigo-500 focus:ring-indigo-500"
          />
          <span className="text-sm text-zinc-700 dark:text-zinc-300">
            {t("config.lightCorrection")}
          </span>
        </label>
      </section>

      {/* 评分维度展示 */}
      <section>
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

      {/* 错误提示 */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </div>
      )}

      {/* 提交按钮 */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={loading}
          className="rounded-xl bg-indigo-500 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition-all hover:bg-indigo-600 disabled:opacity-50 dark:shadow-indigo-900/30"
        >
          {loading
            ? t("config.creating")
            : isInterview
              ? t("config.nextSetup")
              : t("scene.startTraining")}
        </button>
        {isInterview && (
          <span className="text-xs text-zinc-400">{t("scene.requiresResume")}</span>
        )}
        {!isInterview && (
          <span className="text-xs text-amber-500">{t("config.placeholderHint")}</span>
        )}
      </div>
    </div>
  );
}
