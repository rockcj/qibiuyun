"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { listUserSessions, deleteSession } from "@/lib/api";
import type { UserSessionSummary } from "@/types/api";
import Pagination from "@/components/ui/Pagination";
import ConfirmDialog from "@/components/ui/ConfirmDialog";

/** 每页条数 */
const PAGE_SIZE = 5;

/** 场景类型元数据映射 */
const SCENE_META: Record<string, { displayName: string; color: string; iconType: string }> = {
  interview: { displayName: "求职面试", color: "#6366f1", iconType: "briefcase" },
  restaurant: { displayName: "餐厅点餐", color: "#f59e0b", iconType: "utensils" },
  meeting: { displayName: "商务会议", color: "#10b981", iconType: "presentation" },
};

/** 筛选标签配置 */
const FILTER_TABS = [
  { scene: "", label: "全部" },
  { scene: "interview", label: "💼 求职面试" },
  { scene: "restaurant", label: "🍽️ 餐厅点餐" },
  { scene: "meeting", label: "📊 商务会议" },
];

/** 场景几何图标 */
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

/** 格式化日期 */
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getMonth() + 1}月${d.getDate()}日 ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

/** 骨架屏 */
function SkeletonRow() {
  return (
    <div className="flex animate-pulse items-center gap-4 rounded-xl border border-zinc-100 bg-zinc-50 p-4">
      <div className="h-10 w-10 rounded-lg bg-zinc-200" />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-36 rounded bg-zinc-200" />
        <div className="h-3 w-24 rounded bg-zinc-100" />
      </div>
      <div className="h-6 w-16 rounded-full bg-zinc-200" />
    </div>
  );
}

/** 训练记录主页面 — 列表 + 筛选 + 分页 + 删除 */
export default function HistoryPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeScene = searchParams.get("scene") || "";

  const [sessions, setSessions] = useState<UserSessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<UserSessionSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  /** 加载数据 */
  const fetchData = useCallback(
    async (p: number, sceneFilter: string) => {
      setLoading(true);
      setError(null);
      try {
        const sceneParam = sceneFilter || undefined;
        const data = await listUserSessions(PAGE_SIZE, (p - 1) * PAGE_SIZE, sceneParam);
        setSessions(data.sessions);
        setTotal(data.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    setPage(1);
    fetchData(1, activeScene);
  }, [activeScene, fetchData]);

  /** 切换页码 */
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    fetchData(newPage, activeScene);
  };

  /** 切换场景筛选 */
  const handleSceneFilter = (sceneFilter: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (sceneFilter) {
      params.set("scene", sceneFilter);
    } else {
      params.delete("scene");
    }
    router.push(`/history?${params.toString()}`);
  };

  /** 确认删除 */
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteSession(deleteTarget.sessionId);
      setDeleteTarget(null);
      // 刷新当前页
      fetchData(page, activeScene);
    } catch {
      // 忽略，弹窗内不展示错误
    } finally {
      setDeleting(false);
    }
  };

  /** 页面标题和场景中文名 */
  const activeSceneMeta = activeScene ? SCENE_META[activeScene] : null;
  const pageTitle = activeSceneMeta
    ? `${activeSceneMeta.displayName}记录`
    : "全部训练记录";
  const sceneDisplayName = activeSceneMeta?.displayName || "训练";

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 via-indigo-50 to-white">
      {/* 页头 */}
      <header className="relative border-b border-zinc-200/60 bg-white/70 backdrop-blur-xl">
        <div
          className="absolute bottom-0 left-0 right-0 h-0.5"
          style={{
            background: "linear-gradient(90deg, #6366f1 0%, #a855f7 25%, #f59e0b 50%, #10b981 75%, #6366f1 100%)",
            backgroundSize: "200% 100%",
            animation: "gradientFlow 6s ease infinite",
          }}
        />
        <div className="mx-auto flex h-14 max-w-4xl items-center px-6">
          <h1 className="text-lg font-extrabold tracking-tight text-zinc-800">
            📋 {pageTitle}
          </h1>
          <span className="ml-3 text-xs text-zinc-400">
            共 {total} 条
          </span>
        </div>
      </header>

      {/* 主体 */}
      <main className="mx-auto max-w-3xl px-6 py-8">
        {/* 筛选标签 — 仅在无 scene 参数时显示（即"全部"入口） */}
        {!activeScene && (
        <div className="mb-6 flex flex-wrap gap-2">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.scene}
              onClick={() => handleSceneFilter(tab.scene)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-all duration-300 ${
                activeScene === tab.scene
                  ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-lg shadow-indigo-200 scale-105"
                  : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        )}

        {/* 加载态 */}
        {loading && (
          <div className="space-y-3">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        )}

        {/* 错误态 */}
        {!loading && error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center">
            <p className="text-sm font-medium text-red-600">{error}</p>
            <button
              onClick={() => fetchData(page, activeScene)}
              className="mt-3 rounded-xl bg-red-500 px-5 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-red-600"
            >
              重试
            </button>
          </div>
        )}

        {/* 空态 */}
        {!loading && !error && sessions.length === 0 && (
          <div className="rounded-2xl border border-zinc-200 bg-white p-12 text-center shadow-sm">
            <div className="mx-auto mb-3 text-4xl">🔔</div>
            <p className="text-sm font-medium text-zinc-500">
              还没有{sceneDisplayName}记录，开始你的第一次练习吧
            </p>
          </div>
        )}

        {/* 记录列表 */}
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
                  className="group rounded-xl border border-zinc-100 bg-white p-4 shadow-sm transition-all hover:border-zinc-200 hover:shadow-md"
                >
                  <div className="flex items-center gap-4">
                    {/* 场景图标 */}
                    <SceneIcon iconType={meta.iconType} color={meta.color} />

                    {/* 中间信息 */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                          style={{ backgroundColor: `${meta.color}18`, color: meta.color }}
                        >
                          {meta.displayName}
                        </span>
                        <span className="truncate text-sm font-semibold text-zinc-700">
                          {session.topic || "—"}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-zinc-400">
                        <span>📅 {formatDate(session.startedAt || session.endedAt)}</span>
                        <span>⏱ {formatDuration(session.durationSeconds)}</span>
                        {session.roleMode && (
                          <span>🎭 {session.roleMode}</span>
                        )}
                      </div>
                    </div>

                    {/* 右侧操作 */}
                    <div className="flex flex-shrink-0 items-center gap-2">
                      {hasReport && session.sceneScore != null && session.sceneScore > 0 && (
                        <span className="text-lg font-black text-indigo-600">
                          {session.sceneScore}
                        </span>
                      )}
                      {hasReport && (
                        <button
                          onClick={() => router.push(`/reports/${session.sessionId}`)}
                          className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-600 border border-emerald-100 transition-all hover:bg-emerald-100"
                        >
                          查看报告
                          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                      )}
                      {isGenerating && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-600 border border-amber-100">
                          <span className="inline-block h-2 w-2 animate-spin rounded-full border border-amber-400 border-t-transparent" />
                          生成中
                        </span>
                      )}
                      {!hasReport && !isGenerating && session.status === "completed" && (
                        <span className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-400">
                          待生成
                        </span>
                      )}

                      {/* 删除按钮 */}
                      <button
                        onClick={() => setDeleteTarget(session)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-300 transition-all hover:bg-red-50 hover:text-red-500"
                        title="删除记录"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 分页 */}
        {!loading && !error && total > 0 && (
          <div className="mt-8">
            <Pagination
              current={page}
              total={total}
              pageSize={PAGE_SIZE}
              onChange={handlePageChange}
            />
          </div>
        )}
      </main>

      {/* 删除确认弹窗 */}
      <ConfirmDialog
        open={deleteTarget != null}
        title="🗑️ 确认删除"
        message={
          deleteTarget
            ? `确定要删除"${deleteTarget.topic || "未命名"} — ${SCENE_META[deleteTarget.scene]?.displayName || deleteTarget.scene}"这条记录吗？报告和对话数据也会一并删除，此操作不可撤销。`
            : ""
        }
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </div>
  );
}
