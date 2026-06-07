"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listUserSessions } from "@/lib/api";
import type { UserSessionSummary } from "@/types/api";

/** 首页最多展示的最近会话条数 */
const HOME_LIMIT = 5;

/** 场景类型 → 展示名、主题色、几何图标形状 */
const SCENE_META: Record<string, { displayName: string; color: string; iconType: string }> = {
  interview: { displayName: "求职面试", color: "#6366f1", iconType: "briefcase" },
  restaurant: { displayName: "餐厅点餐", color: "#f59e0b", iconType: "utensils" },
  meeting: { displayName: "商务会议", color: "#10b981", iconType: "presentation" },
};

/** 场景图标 — 纯 CSS clip-path 几何形状，简化版 */
function SceneIcon({ iconType, color }: { iconType: string; color: string }) {
  let clipPath = "";
  switch (iconType) {
    case "briefcase":
      clipPath = "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)";
      break;
    case "utensils":
      clipPath = "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)";
      break;
    case "presentation":
      clipPath = "polygon(50% 5%, 95% 90%, 5% 90%)";
      break;
    default:
      clipPath = "circle(50% at 50% 50%)";
      break;
  }

  return (
    <div
      className="flex h-10 w-10 flex-shrink-0 items-center justify-center"
      style={{
        background: `linear-gradient(135deg, ${color}, ${color}cc)`,
        clipPath,
        boxShadow: `0 3px 10px ${color}30`,
      }}
    >
      <div className="h-2 w-2 rounded-full bg-white/40" style={{ filter: "blur(1.5px)" }} />
    </div>
  );
}

/** 格式化秒数为 "X分Y秒" */
function formatDuration(seconds: number | null): string {
  if (seconds == null || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}分${s}秒`;
  return `${s}秒`;
}

/** 格式化 ISO 日期为简短中文显示 */
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  return `${month}月${day}日 ${hours}:${minutes}`;
}

/** 加载骨架屏 */
function SkeletonCard() {
  return (
    <div className="flex animate-pulse items-center gap-4 rounded-xl border border-zinc-100 bg-zinc-50 p-4">
      <div className="h-10 w-10 rounded-lg bg-zinc-200" />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-28 rounded bg-zinc-200" />
        <div className="h-3 w-20 rounded bg-zinc-100" />
      </div>
      <div className="h-6 w-16 rounded-full bg-zinc-200" />
    </div>
  );
}

/**
 * 面试历史记录列表 — 首页"面试记录"区域
 * 仅展示最近 5 条，含场景图标、主题、日期、时长、报告状态/分数
 */
export default function SessionHistoryList() {
  const router = useRouter();
  const [sessions, setSessions] = useState<UserSessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listUserSessions(HOME_LIMIT, 0);
      setSessions(data.sessions);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  /** 卡片点击：有报告则跳转报告页，否则不响应 */
  const handleCardClick = (session: UserSessionSummary) => {
    if (session.reportStatus === "ready") {
      router.push(`/reports/${session.sessionId}`);
    }
  };

  return (
    <div className="w-full">
      {/* 标题行 */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold tracking-tight text-zinc-800">
            📋 面试记录
          </h2>
          {total > 0 && (
            <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-500">
              {total}
            </span>
          )}
        </div>
        {total > HOME_LIMIT && (
          <span className="text-xs font-medium text-zinc-400">
            最近 {HOME_LIMIT} 条
          </span>
        )}
      </div>

      {/* 加载态 */}
      {loading && (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {/* 错误态 */}
      {!loading && error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-600">{error}</p>
          <button
            onClick={fetchSessions}
            className="mt-3 rounded-xl bg-red-500 px-5 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-red-600"
          >
            重试
          </button>
        </div>
      )}

      {/* 空态 */}
      {!loading && !error && sessions.length === 0 && (
        <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-3 text-3xl">🔔</div>
          <p className="text-sm font-medium text-zinc-500">
            还没有面试记录，开始你的第一次练习吧
          </p>
        </div>
      )}

      {/* 会话列表 */}
      {!loading && !error && sessions.length > 0 && (
        <div className="space-y-3">
          {sessions.map((session) => {
            const meta = SCENE_META[session.scene] ?? {
              displayName: session.scene,
              color: "#6b7280",
              iconType: "default",
            };
            const hasReport = session.reportStatus === "ready";
            const isGenerating = session.reportStatus === "generating";

            return (
              <div
                key={session.sessionId}
                onClick={() => handleCardClick(session)}
                className={`group rounded-xl border border-zinc-100 bg-white p-4 shadow-sm transition-all duration-300 ${
                  hasReport
                    ? "cursor-pointer hover:border-indigo-200 hover:shadow-md hover:-translate-y-0.5"
                    : "cursor-default"
                }`}
              >
                <div className="flex items-center gap-4">
                  {/* 场景图标 */}
                  <SceneIcon iconType={meta.iconType} color={meta.color} />

                  {/* 中间信息 */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                        style={{
                          backgroundColor: `${meta.color}18`,
                          color: meta.color,
                        }}
                      >
                        {meta.displayName}
                      </span>
                      <span className="text-sm font-semibold text-zinc-700 truncate">
                        {session.topic || "—"}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400">
                      <span>{formatDate(session.startedAt || session.endedAt)}</span>
                      <span>{formatDuration(session.durationSeconds)}</span>
                    </div>
                  </div>

                  {/* 右侧状态标签 */}
                  <div className="flex flex-shrink-0 items-center gap-2">
                    {hasReport && (
                      <>
                        {session.sceneScore != null && session.sceneScore > 0 && (
                          <span className="text-lg font-black text-indigo-600">
                            {session.sceneScore}
                          </span>
                        )}
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600 border border-emerald-100 transition-all group-hover:bg-emerald-100">
                          查看报告
                          <svg
                            className="h-3 w-3 transition-transform group-hover:translate-x-0.5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2.5}
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                          </svg>
                        </span>
                      </>
                    )}
                    {isGenerating && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-600 border border-amber-100">
                        <span className="inline-block h-2 w-2 animate-spin rounded-full border border-amber-400 border-t-transparent" />
                        生成中
                      </span>
                    )}
                    {!hasReport && !isGenerating && session.status === "completed" && (
                      <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-400">
                        待生成
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
