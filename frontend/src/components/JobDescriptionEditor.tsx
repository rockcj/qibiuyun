"use client";

import { useState } from "react";
import { useLocale } from "@/i18n/LocaleContext";
import { createJob } from "@/lib/api";
import type { JobParsedProfile } from "@/types/api";

interface JobDescriptionEditorProps {
  onCreated: (jobId: string, profile: JobParsedProfile) => void;
}

export default function JobDescriptionEditor({ onCreated }: JobDescriptionEditorProps) {
  const { t } = useLocale();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<JobParsedProfile | null>(null);

  const handleParse = async () => {
    if (!title.trim()) {
      setError(t("jd.error.title"));
      return;
    }
    if (jdText.trim().length < 10) {
      setError(t("jd.error.text"));
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await createJob({
        title: title.trim(),
        company: company.trim(),
        jdText: jdText.trim(),
      });
      setProfile(result.parsedProfile);
      onCreated(result.jobId, result.parsedProfile);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("jd.error.parse"));
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
        {t("jd.title")}
      </h3>
      <p className="mt-1 text-sm text-zinc-500">{t("jd.hint")}</p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400">
            {t("jd.jobTitle")}
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="AI Application Engineer"
            className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400">
            {t("jd.company")}
          </label>
          <input
            type="text"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Demo Company"
            className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
          />
        </div>
      </div>

      <div className="mt-4">
        <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400">
          {t("jd.content")}
        </label>
        <textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          rows={8}
          placeholder={t("jd.placeholder")}
          className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
        />
      </div>

      <button
        type="button"
        onClick={handleParse}
        disabled={loading}
        className="mt-4 rounded-lg bg-indigo-500 px-6 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-600 disabled:opacity-50"
      >
        {loading ? t("jd.parsing") : t("jd.parse")}
      </button>

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {/* 解析结果预览 */}
      {profile && (
        <div className="mt-6 space-y-4">
          <div>
            <h4 className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {t("jd.requiredSkills")}
            </h4>
            <div className="mt-2 flex flex-wrap gap-2">
              {profile.requiredSkills.map((skill) => (
                <span
                  key={skill}
                  className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {t("jd.competencies")}
            </h4>
            <div className="mt-2 flex flex-wrap gap-2">
              {profile.competencies.map((comp) => (
                <span
                  key={comp}
                  className="rounded-full bg-purple-50 px-3 py-1 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
                >
                  {comp}
                </span>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {t("jd.difficulty")}
            </h4>
            <span className="mt-2 inline-block rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
              {profile.difficultyLevel}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
