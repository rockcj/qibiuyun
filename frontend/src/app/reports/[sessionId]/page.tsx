"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import SessionReportPanel from "@/components/SessionReportPanel";
import { getSessionAnalysis, getSessionReport } from "@/lib/api";
import type { SessionAnalysisResponse, SessionReportResponse } from "@/types/api";

/** 课后分析/报告页 */
export default function ReportPage() {
  const { t } = useLocale();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [analysis, setAnalysis] = useState<SessionAnalysisResponse | null>(null);
  const [report, setReport] = useState<SessionReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadReport() {
      setLoading(true);
      setError(null);
      try {
        // 分析数据为主，报告 API 失败时不阻塞页面
        const analysisData = await getSessionAnalysis(sessionId);
        if (cancelled) return;
        setAnalysis(analysisData);

        try {
          const reportData = await getSessionReport(sessionId);
          if (!cancelled) setReport(reportData);
        } catch {
          // 会话可能尚未标记 completed，忽略 report 错误
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("report.error"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    if (sessionId) {
      loadReport();
    }

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">{t("report.loading")}</p>
        </div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-2xl dark:bg-red-900/30">
            ⚠️
          </div>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {error || "未找到分析数据"}
          </p>
          <Link
            href="/"
            className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-500"
          >
            返回首页
          </Link>
        </div>
      </div>
    );
  }

  return (
    <SessionReportPanel
      sessionId={sessionId}
      analysis={analysis}
      report={report}
    />
  );
}
