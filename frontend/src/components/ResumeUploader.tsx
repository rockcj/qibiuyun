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
    <div className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-6">
      <h3 className="text-lg font-bold text-zinc-800">{t("resume.title")}</h3>
      <p className="mt-1 text-sm text-zinc-500">{t("resume.hint")}</p>

      {/* 上传区域 */}
      <div
        className="mt-4 flex flex-1 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-zinc-200 px-6 py-10 transition-all duration-300 hover:border-indigo-400 hover:bg-indigo-50/50"
        onClick={() => inputRef.current?.click()}
      >
        <input ref={inputRef} type="file" accept=".pdf,.txt" className="hidden" onChange={handleFileChange} />
        {loading ? (
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            <p className="text-sm font-medium text-indigo-500">{t("resume.parsing")}</p>
          </div>
        ) : fileName ? (
          <div className="text-center">
            <svg className="mx-auto mb-2 h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm font-medium text-zinc-700">{fileName}</p>
          </div>
        ) : (
          <>
            <svg className="mb-3 h-8 w-8 text-zinc-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-zinc-400">{t("resume.dropzone")}</p>
          </>
        )}
      </div>

      {error && <p className="mt-3 text-sm font-medium text-red-500">{error}</p>}

      {/* 解析结果预览 */}
      {profile && (
        <div className="mt-6 space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-zinc-600">{t("resume.skills")}</h4>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {profile.skills.map((skill) => (
                <span key={skill} className="rounded-full bg-gradient-to-r from-emerald-50 to-teal-50 px-3 py-1 text-xs font-medium text-emerald-700 border border-emerald-100">
                  {skill}
                </span>
              ))}
            </div>
          </div>

          {profile.projects.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-zinc-600">{t("resume.projects")}</h4>
              <ul className="mt-2 space-y-1.5">
                {profile.projects.map((proj) => (
                  <li key={proj.name} className="rounded-lg bg-zinc-50 px-3 py-2 text-sm">
                    <span className="font-medium text-zinc-700">{proj.name}</span>
                    <span className="text-zinc-400"> · {proj.role}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {profile.riskSignals.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-amber-600">{t("resume.risks")}</h4>
              <ul className="mt-2 list-inside list-disc text-sm text-amber-700">
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
