"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Sidebar from "@/components/ui/Sidebar";

/**
 * AppShell — 客户端布局外壳
 * 根据认证状态和当前路径决定是否显示全局侧边栏：
 * - 未登录 → 无侧边栏
 * - /login, /register → 无侧边栏
 * - /sessions/*, /reports/* → 无侧边栏（沉浸式体验）
 * - 其他路径 → 显示侧边栏
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const pathname = usePathname();

  // 不显示侧边栏的路径
  const hideSidebarPaths = ["/login", "/register"];
  const hideSidebarPrefixes = ["/sessions/", "/reports/"];

  const shouldShowSidebar =
    isAuthenticated &&
    !hideSidebarPaths.includes(pathname) &&
    !hideSidebarPrefixes.some((prefix) => pathname.startsWith(prefix));

  if (!shouldShowSidebar) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Suspense fallback={<div className="w-[220px] flex-shrink-0 bg-white border-r border-zinc-200" />}>
        <Sidebar />
      </Suspense>
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
