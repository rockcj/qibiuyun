"use client";

import { Suspense } from "react";
import HistoryPage from "@/components/HistoryPage";

/**
 * /history 路由 — 训练记录页面
 * Suspense 包裹是因为 HistoryPage 内部使用了 useSearchParams()
 */
export default function HistoryPageRoute() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-white">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        </div>
      }
    >
      <HistoryPage />
    </Suspense>
  );
}
