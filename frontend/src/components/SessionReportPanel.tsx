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
import TranscriptReplayPanel from "./TranscriptReplayPanel";

interface SessionReportPanelProps {
  sessionId: string;
  analysis: SessionAnalysisResponse;
  report: SessionReportResponse | null;
  timelineEvents: SessionEventsResponse | null;
  reportStatus: "loading" | "generating" | "ready" | "error";
  highlightTurnId?: string | null;
  onTimelineEventClick?: (event: TimelineEventItem) => void;
}

/** 严重程度标签样式 */
function severityBadge(severity: string) {
  if (severity === "serious") {
    return "bg-red-100 text-red-700 border border-red-200";
  }
  if (severity === "minor") {
    return "bg-amber-100 text-amber-700 border border-amber-200";
  }
  return "bg-zinc-100 text-zinc-600 border border-zinc-200";
}

/** 课后分析/报告面板 */
export default function SessionReportPanel({
  sessionId,
  analysis,
  report,
  timelineEvents,
  reportStatus,
  highlightTurnId,
  onTimelineEventClick,
}: SessionReportPanelProps) {
  const { t } = useLocale();

  const transcriptTurns = analysis.transcriptTurns ?? [];
  const totalFillers = Object.values(analysis.fillerCounts).reduce((a, b) => a + b, 0);
  const avgWpm =
    analysis.pronunciation.length > 0
      ? (
          analysis.pronunciation.reduce((sum, p) => sum + p.wordsPerMinute, 0) /
          analysis.pronunciation.length
        ).toFixed(1)
      : "—";
  const totalPauses = analysis.pronunciation.reduce((sum, p) => sum + p.pauseCount, 0);

  const hasAnalysisDetail =
    analysis.pronunciation.length > 0 ||
    analysis.corrections.length > 0 ||
    totalFillers > 0;
  const hasTranscript = transcriptTurns.length > 0;
  const hasTimeline = (timelineEvents?.events.length ?? 0) > 0;
  const hasReport = reportStatus === "ready" && report != null;
  const showEmptyHint = !hasAnalysisDetail && !hasTranscript && !hasTimeline && !hasReport;

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
      {/* 页头 */}
      <header className="relative border-b border-zinc-200/60 bg-white/70 backdrop-blur-xl">
        <div className="absolute bottom-0 left-0 right-0 h-0.5"
          style={{ background: "linear-gradient(90deg, #6366f1 0%, #a855f7 25%, #f59e0b 50%, #10b981 75%, #6366f1 100%)", backgroundSize: "200% 100%", animation: "gradientFlow 6s ease infinite" }} />
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <Link href="/" className="text-sm font-medium text-zinc-500 transition-colors hover:text-indigo-500">
            {t("scene.backHome")}
          </Link>
          <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-500">
            {t("report.sessionId")}: {sessionId.slice(0, 8)}…
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-3xl font-extrabold tracking-tight text-zinc-900">{t("report.title")}</h1>
        <p className="mt-2 text-zinc-500">{t("report.subtitle")}</p>

        {/* 报告生成中 */}
        {reportStatus === "generating" && (
          <section className="mt-6 rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-yellow-50 p-8 text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <h2 className="text-lg font-bold text-amber-800">{t("report.generating")}</h2>
            <p className="mt-2 text-sm text-amber-700">{t("report.generatingHint")}</p>
          </section>
        )}

        {/* 报告加载失败 */}
        {reportStatus === "error" && (
          <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-sm font-medium text-red-600">{t("report.error")}</p>
            <button onClick={() => window.location.reload()}
              className="mt-3 rounded-xl bg-red-500 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-red-200 transition-all hover:bg-red-600 hover:shadow-lg">
              {t("report.retry")}
            </button>
          </section>
        )}

        {/* Offer Score + 雷达图 */}
        {report && reportStatus === "ready" && (
          <section className="mt-6 rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-purple-50 p-6 shadow-sm">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-indigo-800">{report.scoreName}</h2>
                <p className="mt-2 text-sm text-indigo-700">{report.finalRecommendation}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-indigo-500">Offer Score</span>
                <p className="text-5xl font-black text-indigo-600">{report.sceneScore}</p>
              </div>
            </div>

            {Object.keys(report.dimensionScores).length >= 3 && (
              <div className="mt-6 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
                <div className="flex-shrink-0">
                  <RadarChart
                    dimensions={Object.entries(report.dimensionScores).map(([key, score]) => ({
                      key, label: t(`report.dimension.${key}` as never) ?? key, score,
                    }))}
                    size={240}
                  />
                </div>
                <div className="grid flex-1 grid-cols-2 gap-2 content-start">
                  {Object.entries(report.dimensionScores).map(([key, score]) => (
                    <div key={key} className="rounded-xl bg-white/80 p-3 shadow-sm">
                      <p className="text-xs font-medium text-zinc-500">{t(`report.dimension.${key}` as never) ?? key}</p>
                      <p className="text-xl font-bold text-indigo-700">{score}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(report.dimensionScores).length > 0 && Object.keys(report.dimensionScores).length < 3 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {Object.entries(report.dimensionScores).map(([key, score]) => (
                  <span key={key} className="rounded-full bg-white/80 px-3.5 py-1.5 text-xs font-semibold text-indigo-700 shadow-sm">
                    {t(`report.dimension.${key}` as never) ?? key}: {score}
                  </span>
                ))}
              </div>
            )}

            {(report.highlights?.length || report.improvements?.length) ? (
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {report.highlights && report.highlights.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-indigo-500">{t("report.highlights")}</p>
                    <ul className="mt-2 space-y-1">
                      {report.highlights.map((item) => (
                        <li key={item} className="flex items-start gap-2 text-sm text-indigo-800">
                          <span className="mt-0.5 text-emerald-500">✦</span> {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.improvements && report.improvements.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-indigo-500">{t("report.improvements")}</p>
                    <ul className="mt-2 space-y-1">
                      {report.improvements.map((item) => (
                        <li key={item} className="flex items-start gap-2 text-sm text-indigo-800">
                          <span className="mt-0.5 text-amber-500">→</span> {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </section>
        )}

        {/* 语气分析概览 */}
        {!showEmptyHint && (
          <section className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium text-zinc-400">{t("report.avgWpm")}</p>
              <p className="mt-1 text-3xl font-bold text-zinc-900">{avgWpm}</p>
            </div>
            <div className="rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium text-zinc-400">{t("report.totalPauses")}</p>
              <p className="mt-1 text-3xl font-bold text-zinc-900">{totalPauses}</p>
            </div>
            <div className="rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium text-zinc-400">{t("report.correctionCount")}</p>
              <p className="mt-1 text-3xl font-bold text-zinc-900">
                {analysis.corrections.length}
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium text-zinc-400">{t("report.fillerTotal")}</p>
              <p className="mt-1 text-3xl font-bold text-zinc-900">{totalFillers}</p>
            </div>
          </section>
        )}

        {showEmptyHint && (
          <div className="mt-8 rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
            <p className="text-sm font-medium text-zinc-500">{t("report.noData")}</p>
          </div>
        )}

        {/* 证据列表 */}
        {report?.evidenceList && report.evidenceList.length > 0 && (
          <section className="mt-10">
            <h2 className="text-xl font-bold tracking-tight text-zinc-800">{t("report.evidence")}</h2>
            <div className="mt-3 space-y-3">
              {report.evidenceList.map((item) => (
                <div key={item.dimension} className="rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-600">
                      {t(`report.dimension.${item.dimension}` as never) ?? item.dimension}
                    </span>
                    <span className="text-sm font-bold text-zinc-700">{item.score}/100</span>
                  </div>
                  {item.evidence && <p className="text-sm leading-relaxed text-zinc-600">{item.evidence}</p>}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* VAR 时间轴 */}
        {timelineEvents && (
          <section className="mt-10">
            <h2 className="text-xl font-bold tracking-tight text-zinc-800">{t("report.timeline")}</h2>
            <div className="mt-3">
              <TimelineViewer events={timelineEvents.events} onEventClick={onTimelineEventClick} t={t as (key: string) => string} />
            </div>
          </section>
        )}

        {/* 对话回放 */}
        {(hasTranscript || reportStatus !== "loading") && (
          <section className="mt-10">
            <h2 className="text-xl font-bold tracking-tight text-zinc-800">{t("report.transcriptSection")}</h2>
            <div className="mt-3">
              <TranscriptReplayPanel
                turns={transcriptTurns}
                highlightTurnId={highlightTurnId}
                fullAudioUrl={analysis.fullAudioUrl}
                t={t as (key: string) => string}
              />
            </div>
          </section>
        )}

        {/* 语气词统计 */}
        {totalFillers > 0 && (
          <section className="mt-10">
            <h2 className="text-xl font-bold tracking-tight text-zinc-800">{t("report.fillerSection")}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(analysis.fillerCounts).map(([word, count]) => (
                <span key={word} className="rounded-full bg-zinc-100 px-3.5 py-1.5 text-sm font-medium text-zinc-600 border border-zinc-200">
                  {word}: <span className="font-bold text-zinc-800">{count}</span>
                </span>
              ))}
            </div>
          </section>
        )}

        {/* 发音分析 */}
        {analysis.pronunciation.length > 0 && (
          <section className="mt-10">
            <h2 className="text-xl font-bold tracking-tight text-zinc-800">{t("report.pronunciationSection")}</h2>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-zinc-200 shadow-sm">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs font-semibold uppercase text-zinc-500">
                  <tr>
                    <th className="px-4 py-3.5">{t("report.turn")}</th>
                    <th className="px-4 py-3.5">{t("report.wpm")}</th>
                    <th className="px-4 py-3.5">{t("report.pauses")}</th>
                    <th className="px-4 py-3.5">{t("report.duration")}</th>
                    <th className="px-4 py-3.5">{t("report.lowConfWords")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {analysis.pronunciation.map((row) => (
                    <tr key={row.turnId} className="bg-white hover:bg-zinc-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-zinc-400">{row.turnId}</td>
                      <td className="px-4 py-3 font-medium">{row.wordsPerMinute}</td>
                      <td className="px-4 py-3">{row.pauseCount}</td>
                      <td className="px-4 py-3">
                        {row.durationSeconds != null ? `${row.durationSeconds}s` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {row.lowConfidenceWords.length > 0 ? (
                          <span className="font-medium text-amber-600">{row.lowConfidenceWords.join(", ")}</span>
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

        {/* 语法纠正记录 */}
        {analysis.corrections.length > 0 && (
          <section className="mt-10">
            <h2 className="text-xl font-bold tracking-tight text-zinc-800">{t("report.correctionSection")}</h2>
            <div className="mt-3 space-y-3">
              {analysis.corrections.map((item, idx) => (
                <div key={`${item.turnId}-${idx}`} className="rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-400">{item.turnId}</span>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${severityBadge(item.severity)}`}>
                      {item.severity === "serious"
                        ? t("report.severitySerious")
                        : item.severity === "minor"
                          ? t("report.severityMinor")
                          : item.severity}
                    </span>
                  </div>
                  {item.transcript && (
                    <p className="mt-2 text-sm italic text-zinc-600">&ldquo;{item.transcript}&rdquo;</p>
                  )}
                  <p className="mt-2 text-sm">
                    <span className="line-through text-red-400">{item.original}</span>
                    {" → "}
                    <span className="font-semibold text-emerald-600">{item.corrected}</span>
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 返回首页 */}
        <div className="mt-12 pb-8 text-center">
          <Link href="/"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 px-8 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-200 transition-all hover:shadow-xl hover:shadow-indigo-300 hover:scale-[1.03]">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            {t("report.backHome")}
          </Link>
        </div>
      </main>
    </div>
  );
}
