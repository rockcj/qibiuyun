"use client";

/** 纯 SVG 雷达图组件 — 无 npm 依赖 */

interface Dimension {
  key: string;
  label: string;
  score: number;
}

interface RadarChartProps {
  dimensions: Dimension[];
  size?: number;
  maxScore?: number;
  className?: string;
}

/** 根据索引和总数计算顶点坐标 */
function getVertex(
  index: number,
  total: number,
  value: number,
  center: number,
  radius: number
): { x: number; y: number } {
  const angle = (2 * Math.PI * index) / total - Math.PI / 2;
  return {
    x: center + radius * value * Math.cos(angle),
    y: center + radius * value * Math.sin(angle),
  };
}

/** 生成多边形 points 属性字符串 */
function polygonPoints(
  total: number,
  value: number,
  center: number,
  radius: number
): string {
  return Array.from({ length: total }, (_, i) => {
    const v = getVertex(i, total, value, center, radius);
    return `${v.x},${v.y}`;
  }).join(" ");
}

export default function RadarChart({
  dimensions,
  size = 280,
  maxScore = 100,
  className = "",
}: RadarChartProps) {
  const center = size / 2;
  const radius = size / 2 - 32;
  const total = dimensions.length;

  if (total < 3) {
    return (
      <div
        className={`flex items-center justify-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
        style={{ width: size, height: size }}
      >
        <p className="text-xs text-zinc-400">Need at least 3 dimensions</p>
      </div>
    );
  }

  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <div className={`flex justify-center ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="overflow-visible"
      >
        {/* 同心多边形网格 */}
        {gridLevels.map((level) => (
          <polygon
            key={level}
            points={polygonPoints(total, level, center, radius)}
            fill="none"
            stroke="currentColor"
            className="text-zinc-200 dark:text-zinc-700"
            strokeWidth="1"
          />
        ))}

        {/* 轴线 */}
        {Array.from({ length: total }, (_, i) => {
          const v = getVertex(i, total, 1, center, radius);
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={v.x}
              y2={v.y}
              stroke="currentColor"
              className="text-zinc-200 dark:text-zinc-700"
              strokeWidth="1"
            />
          );
        })}

        {/* 分数多边形 */}
        <polygon
          points={dimensions
            .map((d, i) => {
              const v = getVertex(i, total, d.score / maxScore, center, radius);
              return `${v.x},${v.y}`;
            })
            .join(" ")}
          fill="rgba(99, 102, 241, 0.15)"
          stroke="rgb(99, 102, 241)"
          strokeWidth="2"
        />

        {/* 分数圆点 */}
        {dimensions.map((d, i) => {
          const v = getVertex(i, total, d.score / maxScore, center, radius);
          return (
            <circle
              key={i}
              cx={v.x}
              cy={v.y}
              r="4"
              fill="rgb(99, 102, 241)"
              className="dark:fill-indigo-400"
            />
          );
        })}

        {/* 标签 */}
        {dimensions.map((d, i) => {
          const v = getVertex(i, total, 1.15, center, radius);
          return (
            <text
              key={i}
              x={v.x}
              y={v.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-zinc-600 text-[11px] dark:fill-zinc-400"
              style={{ fontFamily: "system-ui, sans-serif" }}
            >
              {d.label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
