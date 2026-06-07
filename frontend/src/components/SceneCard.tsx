"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";

/** 场景卡片数据 */
export interface SceneCardData {
  scene: string;
  displayName: string;
  description: string;
  icon: string;
  color: string;
  enabled?: boolean;
  releasePriority?: string;
  disabledReason?: string;
}

interface SceneCardProps {
  scene: SceneCardData;
  index: number;
}

/**
 * 渐变几何图标 — 纯 CSS 形状 + 渐变色，替代 emoji
 * 根据 icon 名称返回不同的几何形状
 */
function GeometricIcon({ icon, color }: { icon: string; color: string }) {
  // 各场景的几何形状
  let clipPath = "";
  switch (icon) {
    case "briefcase":
      // 六边形 — 稳定、专业，适合面试
      clipPath = "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)";
      break;
    case "utensils":
      // 菱形 — 锐利、活泼，适合餐厅
      clipPath = "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)";
      break;
    case "presentation":
      // 向上的三角形 — 成长、上升，适合商务会议
      clipPath = "polygon(50% 5%, 95% 90%, 5% 90%)";
      break;
    default:
      // 默认：圆形
      clipPath = "circle(50% at 50% 50%)";
      break;
  }

  return (
    <div
      className="flex h-14 w-14 items-center justify-center"
      style={{
        background: `linear-gradient(135deg, ${color}, ${color}cc)`,
        clipPath,
        boxShadow: `0 4px 16px ${color}40`,
      }}
    >
      {/* 内部小高光 */}
      <div
        className="h-3 w-3 rounded-full bg-white/40"
        style={{ filter: "blur(2px)" }}
      />
    </div>
  );
}

/**
 * 获取场景卡片的软渐变背景色
 */
function getCardGradient(color: string): string {
  // 根据主色生成柔和渐变背景
  return `linear-gradient(135deg, ${color}10 0%, ${color}20 30%, ${color}08 100%)`;
}

/**
 * 场景卡片组件 — 活泼多彩风格
 * 独立软渐变背景 + CSS 几何图标 + 弹性 hover 动画
 */
export default function SceneCard({ scene, index }: SceneCardProps) {
  const router = useRouter();
  const { t } = useLocale();

  const isEnabled = scene.enabled !== false;

  const handleClick = () => {
    if (!isEnabled) return;
    router.push(`/scenes/${scene.scene}`);
  };

  return (
    <button
      onClick={handleClick}
      disabled={!isEnabled}
      className={`group relative w-full max-w-sm cursor-pointer text-left transition-all duration-500 scene-card-enter ${
        isEnabled
          ? "hover:scale-[1.03] hover:-translate-y-1.5"
          : "cursor-not-allowed"
      }`}
      style={{
        animationDelay: `${index * 120}ms`,
      }}
    >
      {/* 卡片主体 */}
      <div
        className="relative overflow-hidden rounded-3xl border p-8"
        style={{
          background: getCardGradient(scene.color),
          borderColor: `${scene.color}30`,
          boxShadow: isEnabled
            ? `0 2px 12px ${scene.color}10, 0 1px 3px rgba(0,0,0,0.04)`
            : "none",
          transition: "all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)",
        }}
      >
        {/* Hover 时的渐变覆盖层 */}
        <div
          className="absolute inset-0 rounded-3xl opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            background: `linear-gradient(135deg, ${scene.color}18, ${scene.color}28, ${scene.color}10)`,
          }}
        />

        {/* 右上角装饰光斑 */}
        <div
          className="absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-20 transition-all duration-500 group-hover:scale-125 group-hover:opacity-35"
          style={{ background: `radial-gradient(circle, ${scene.color}, transparent)` }}
        />

        {/* 内容区 */}
        <div className="relative z-10">
          {/* 几何图标 */}
          <div className="mb-5">
            <GeometricIcon icon={scene.icon} color={scene.color} />
          </div>

          {/* 标题 */}
          <h3
            className="mb-2 text-xl font-extrabold tracking-tight transition-colors duration-300"
            style={{ color: `${scene.color}dd` }}
          >
            {scene.displayName}
          </h3>

          {/* 描述 */}
          <p className="text-sm leading-relaxed text-zinc-500 line-clamp-2">
            {scene.description}
          </p>

          {/* 未启用标签 */}
          {!isEnabled && (
            <div className="mt-4 flex flex-wrap gap-2">
              {scene.releasePriority && (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-zinc-500 backdrop-blur-sm">
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: scene.color }}
                  />
                  {scene.releasePriority}
                </span>
              )}
              {scene.disabledReason && (
                <span className="inline-flex items-center rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-zinc-400 backdrop-blur-sm">
                  {scene.disabledReason}
                </span>
              )}
            </div>
          )}

          {/* CTA — 仅启用卡片显示 */}
          {isEnabled && (
            <div
              className="mt-6 flex items-center gap-2 text-sm font-bold transition-all duration-300 group-hover:gap-3"
              style={{ color: scene.color }}
            >
              <span>{t("scene.startTraining")}</span>
              <svg
                className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </div>
          )}
        </div>
      </div>

      {/* Hover 发光边框效果 */}
      {isEnabled && (
        <div
          className="absolute inset-0 rounded-3xl opacity-0 transition-opacity duration-500 group-hover:opacity-100 pointer-events-none"
          style={{
            boxShadow: `0 0 0 2px ${scene.color}40, 0 8px 32px ${scene.color}20`,
          }}
        />
      )}
    </button>
  );
}
