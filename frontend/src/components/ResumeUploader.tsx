"use client";

import { useRef, useState } from "react";
import { useLocale } from "@/i18n/LocaleContext";
import { uploadResume } from "@/lib/api";
import type { ResumeParsedProfile } from "@/types/api";

interface ResumeUploaderProps {
  onUploaded: (resumeId: string, profile: ResumeParsedProfile) => void;
}

export default function ResumeUploader({ onUploaded }: ResumeUploaderProps) {
  const { t } = useLocale();
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<ResumeParsedProfile | null>(null);
  const [fileName, setFileName] = useState("");

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 校验文件类型
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "txt"].includes(ext || "")) {
      setError(t("resume.error.type"));
      return;
    }

    setLoading(true);
    setError("");
    setFileName(file.name);

    try {
      const result = await uploadResume(file);
      setProfile(result.parsedProfile);
      onUploaded(result.resumeId, result.parsedProfile);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("resume.error.upload"));
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
        {t("resume.title")}
      </h3>
      <p className="mt-1 text-sm text-zinc-500">{t("resume.hint")}</p>

      {/* 上传区域 */}
      <div
        className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-zinc-200 px-6 py-10 transition-colors hover:border-indigo-400 hover:bg-indigo-50/50 dark:border-zinc-700 dark:hover:border-indigo-500 dark:hover:bg-indigo-900/10"
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={handleFileChange}
        />
        {loading ? (
          <p className="text-sm text-indigo-500">{t("resume.parsing")}</p>
        ) : fileName ? (
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{fileName}</p>
        ) : (
          <>
            <svg
              className="mb-2 h-8 w-8 text-zinc-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <p className="text-sm text-zinc-500">{t("resume.dropzone")}</p>
          </>
        )}
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {/* 解析结果预览 */}
      {profile && (
        <div className="mt-6 space-y-4">
          <div>
            <h4 className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {t("resume.skills")}
            </h4>
            <div className="mt-2 flex flex-wrap gap-2">
              {profile.skills.map((skill) => (
                <span
                  key={skill}
                  className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>

          {profile.projects.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                {t("resume.projects")}
              </h4>
              <ul className="mt-2 space-y-2">
                {profile.projects.map((proj) => (
                  <li
                    key={proj.name}
                    className="rounded-lg bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-800"
                  >
                    <span className="font-medium">{proj.name}</span>
                    <span className="text-zinc-500"> · {proj.role}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {profile.riskSignals.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-amber-600 dark:text-amber-400">
                {t("resume.risks")}
              </h4>
              <ul className="mt-2 list-inside list-disc text-sm text-amber-700 dark:text-amber-300">
                {profile.riskSignals.map((risk) => (
                  <li key={risk}>{risk}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
