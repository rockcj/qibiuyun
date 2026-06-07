"use client";

interface PaginationProps {
  current: number;   // 当前页码（1-based）
  total: number;     // 总记录条数
  pageSize: number;  // 每页条数
  onChange: (page: number) => void;
}

/**
 * 通用分页组件
 * 显示：← 1 2 3 ... N → ，当前页 indigo 高亮
 */
export default function Pagination({
  current,
  total,
  pageSize,
  onChange,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (totalPages <= 1) return null;

  /** 生成页码数组 */
  function buildPages(): (number | "...")[] {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    const pages: (number | "...")[] = [];
    // 始终显示第一页
    pages.push(1);

    if (current > 3) {
      pages.push("...");
    }

    // 当前页附近的页码
    const start = Math.max(2, current - 1);
    const end = Math.min(totalPages - 1, current + 1);
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (current < totalPages - 2) {
      pages.push("...");
    }

    // 始终显示最后一页
    if (totalPages > 1) {
      pages.push(totalPages);
    }

    return pages;
  }

  const pages = buildPages();

  return (
    <div className="flex items-center justify-center gap-1.5">
      {/* 上一页 */}
      <button
        onClick={() => onChange(current - 1)}
        disabled={current <= 1}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-sm text-zinc-500 transition-all hover:border-zinc-300 hover:text-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
      >
        ←
      </button>

      {/* 页码 */}
      {pages.map((page, idx) =>
        page === "..." ? (
          <span key={`dots-${idx}`} className="px-1 text-sm text-zinc-400">
            ...
          </span>
        ) : (
          <button
            key={page}
            onClick={() => onChange(page as number)}
            className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-semibold transition-all ${
              page === current
                ? "bg-indigo-500 text-white shadow-sm shadow-indigo-200"
                : "border border-zinc-200 bg-white text-zinc-500 hover:border-zinc-300 hover:text-zinc-700"
            }`}
          >
            {page}
          </button>
        )
      )}

      {/* 下一页 */}
      <button
        onClick={() => onChange(current + 1)}
        disabled={current >= totalPages}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-sm text-zinc-500 transition-all hover:border-zinc-300 hover:text-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
      >
        →
      </button>

      {/* 总数提示 */}
      <span className="ml-3 text-xs text-zinc-400">
        共 {total} 条
      </span>
    </div>
  );
}
