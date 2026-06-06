"use client";

import Link from "next/link";
import { useLocale } from "@/i18n/LocaleContext";
import type {
  SessionAnalysisResponse,
  SessionEventsResponse,
  SessionReportResponse,
  TimelineEventItem,
} from "@/types/api";
import RadarChart from "./RadarChart";
import TimelineViewer from "./TimelineViewer";

interface SessionReportPanelProps {
  sessionId: string;
  analysis: SessionAnalysisResponse;
  report: SessionReportResponse | null;
  timelineEvents: SessionEventsResponse | null;
  reportStatus: "loading" | "generating" | "ready" | "error";
  onTimelineEventClick?: (event: TimelineEventItem) => void;
}

/** 严重程度标签样式 */
function severityBadge(severity: string) {
  if (severity === "serious") {
    return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
  }
  if (severity === "minor") {
    return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
  }
  return "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";
}

/** 课后分析/报告面板 */
export default function SessionReportPanel({
  sessionId,
  analysis,
  report,
  timelineEvents,
  reportStatus,
  onTimelineEventClick,
}: SessionReportPanelProps) {
  const { t } = useLocale();

  const totalFillers = Object.values(analysis.fillerCounts).reduce((a, b) => a + b, 0);
  const avgWpm =
    analysis.pronunciation.length > 0
      ? (
          analysis.pronunciation.reduce((sum, p) => sum + p.wordsPerMinute, 0) /
          analysis.pronunciation.length
        ).toFixed(1)
      : "—";
  const totalPauses = analysis.pronunciation.reduce((sum, p) => sum + p.pauseCount, 0);

  const hasData =
    analysis.pronunciation.length > 0 ||
    analysis.corrections.length > 0 ||
    totalFillers > 0;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      {/* 页头 */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6">
          <Link
            href="/"
            className="text-sm text-zinc-500 transition-colors hover:text-zinc-900 dark:hover:text-white"
          >
            {t("scene.backHome")}
          </Link>
          <span className="text-xs text-zinc-400">
            {t("report.sessionId")}: {sessionId.slice(0, 8)}…
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          {t("report.title")}
        </h1>
        <p className="mt-2 text-sm text-zinc-500">{t("report.subtitle")}</p>

        {/* 报告生成中 */}
        {reportStatus === "generating" && (
          <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center dark:border-amber-800 dark:bg-amber-950/30">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <h2 className="text-lg font-semibold text-amber-800 dark:text-amber-200">
              {t("report.generating")}
            </h2>
            <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
              {t("report.generatingHint")}
            </p>
          </section>
        )}

        {/* 报告加载失败 */}
        {reportStatus === "error" && (
          <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-950/30">
            <p className="text-sm text-red-700 dark:text-red-300">
              {t("report.error")}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="mt-3 rounded-xl bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600"
            >
              {t("report.retry")}
            </button>
          </section>
        )}

        {/* Offer Score + 雷达图 */}
        {report && reportStatus === "ready" && (
          <section className="mt-6 rounded-2xl border border-indigo-200 bg-indigo-50 p-6 dark:border-indigo-800 dark:bg-indigo-950/30">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-indigo-800 dark:text-indigo-200">
                  {report.scoreName}
                </h2>
                <p className="mt-2 text-sm text-indigo-700 dark:text-indigo-300">
                  {report.finalRecommendation}
                </p>
              </div>
              <p className="text-5xl font-bold text-indigo-600 dark:text-indigo-300">
                {report.sceneScore}
              </p>
            </div>

            {/* 雷达图 + 维度分 */}
            {Object.keys(report.dimensionScores).length >= 3 && (
              <div className="mt-6 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
                <div className="flex-shrink-0">
                  <RadarChart
                    dimensions={Object.entries(report.dimensionScores).map(([key, score]) => ({
                      key,
                      label: t(`report.dimension.${key}` as Parameters<typeof t>[0]) ?? key,
                      score,
                    }))}
                    size={240}
                  />
                </div>
                {/* 维度分列表 */}
                <div className="grid flex-1 grid-cols-2 gap-2 content-start">
                  {Object.entries(report.dimensionScores).map(([key, score]) => (
                    <div
                      key={key}
                      className="rounded-lg bg-white/70 px-3 py-2 dark:bg-indigo-900/30"
                    >
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                        {t(`report.dimension.${key}` as Parameters<typeof t>[0]) ?? key}
                      </p>
                      <p className="text-lg font-bold text-indigo-700 dark:text-indigo-300">
                        {score}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 小维度数时只显示标签 */}
            {Object.keys(report.dimensionScores).length > 0 &&
              Object.keys(report.dimensionScores).length < 3 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {Object.entries(report.dimensionScores).map(([key, score]) => (
                    <span
                      key={key}
                      className="rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-200"
                    >
                      {t(`report.dimension.${key}` as Parameters<typeof t>[0]) ?? key}: {score}
                    </span>
                  ))}
                </div>
              )}

            {(report.highlights?.length || report.improvements?.length) ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {report.highlights && report.highlights.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase text-indigo-600 dark:text-indigo-300">
                      {t("report.highlights")}
                    </p>
                    <ul className="mt-2 list-inside list-disc text-sm text-indigo-800 dark:text-indigo-200">
                      {report.highlights.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.improvements && report.improvements.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase text-indigo-600 dark:text-indigo-300">
                      {t("report.improvements")}
                    </p>
                    <ul className="mt-2 list-inside list-disc text-sm text-indigo-800 dark:text-indigo-200">
                      {report.improvements.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </section>
        )}

        {/* 证据列表 */}
        {report?.evidenceList && report.evidenceList.length > 0 && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              {t("report.evidence")}
            </h2>
            <div className="mt-3 space-y-3">
              {report.evidenceList.map((item) => (
                <div
                  key={item.dimension}
                  className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                      {t(`report.dimension.${item.dimension}` as Parameters<typeof t>[0]) ?? item.dimension}
                    </span>
                    <span className="text-sm font-bold text-zinc-700 dark:text-zinc-300">
                      {item.score}/100
                    </span>
                  </div>
                  {item.evidence && (
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                      {item.evidence}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* VAR 时间轴 */}
        {timelineEvents && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              {t("report.timeline")}
            </h2>
            <div className="mt-3">
              <TimelineViewer
                events={timelineEvents.events}
                onEventClick={onTimelineEventClick}
                t={t as (key: string) => string}
              />
            </div>
          </section>
        )}

        {/* 概览卡片 */}
        <section className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-xs text-zinc-400">{t("report.avgWpm")}</p>
            <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">{avgWpm}</p>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-xs text-zinc-400">{t("report.totalPauses")}</p>
            <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">{totalPauses}</p>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-xs text-zinc-400">{t("report.correctionCount")}</p>
            <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {analysis.corrections.length}
            </p>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-xs text-zinc-400">{t("report.fillerTotal")}</p>
            <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">{totalFillers}</p>
          </div>
        </section>

        {!hasData && (
          <div className="mt-8 rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-sm text-zinc-500">{t("report.noData")}</p>
          </div>
        )}

        {/* 语气词统计 */}
        {totalFillers > 0 && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              {t("report.fillerSection")}
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(analysis.fillerCounts).map(([word, count]) => (
                <span
                  key={word}
                  className="rounded-full bg-zinc-100 px-3 py-1 text-sm font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  {word}: {count}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* 发音分析 */}
        {analysis.pronunciation.length > 0 && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              {t("report.pronunciationSection")}
            </h2>
            <div className="mt-3 overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-4 py-3">{t("report.turn")}</th>
                    <th className="px-4 py-3">{t("report.wpm")}</th>
                    <th className="px-4 py-3">{t("report.pauses")}</th>
                    <th className="px-4 py-3">{t("report.duration")}</th>
                    <th className="px-4 py-3">{t("report.lowConfWords")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {analysis.pronunciation.map((row) => (
                    <tr key={row.turnId} className="bg-white dark:bg-zinc-950">
                      <td className="px-4 py-3 font-mono text-xs text-zinc-500">{row.turnId}</td>
                      <td className="px-4 py-3">{row.wordsPerMinute}</td>
                      <td className="px-4 py-3">{row.pauseCount}</td>
                      <td className="px-4 py-3">
                        {row.durationSeconds != null ? `${row.durationSeconds}s` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {row.lowConfidenceWords.length > 0 ? (
                          <span className="text-amber-600 dark:text-amber-400">
                            {row.lowConfidenceWords.join(", ")}
                          </span>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* 语法纠正记录（含轻微错误） */}
        {analysis.corrections.length > 0 && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              {t("report.correctionSection")}
            </h2>
            <div className="mt-3 space-y-3">
              {analysis.corrections.map((item, idx) => (
                <div
                  key={`${item.turnId}-${idx}`}
                  className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-400">{item.turnId}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${severityBadge(item.severity)}`}
                    >
                      {item.severity === "serious"
                        ? t("report.severitySerious")
                        : item.severity === "minor"
                          ? t("report.severityMinor")
                          : item.severity}
                    </span>
                  </div>
                  {item.transcript && (
                    <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                      &ldquo;{item.transcript}&rdquo;
                    </p>
                  )}
                  <p className="mt-2 text-sm">
                    <span className="line-through text-red-500">{item.original}</span>
                    {" → "}
                    <span className="font-medium text-emerald-600 dark:text-emerald-400">
                      {item.corrected}
                    </span>
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 返回首页 */}
        <div className="mt-10 pb-8">
          <Link
            href="/"
            className="inline-block rounded-xl bg-indigo-500 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-600"
          >
            {t("report.backHome")}
          </Link>
        </div>
      </main>
    </div>
  );
}
