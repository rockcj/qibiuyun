"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

/** 全局侧边栏 — 登录后主要页面左侧显示，220px 宽 */
export default function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, logout } = useAuth();

  const activeScene = searchParams.get("scene") || "";

  const isActive = (href: string) => {
    if (href === "/history") {
      return pathname.startsWith("/history");
    }
    return pathname === href;
  };

  /** 记录菜单项是否高亮：当前在 /history 且 scene 参数匹配 */
  const isRecordActive = (scene: string) => {
    return pathname.startsWith("/history") && activeScene === scene;
  };

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  // 场景记录菜单项
  const recordLinks = [
    { scene: "interview", label: "💼 面试记录", href: "/history?scene=interview", disabled: false },
    { scene: "restaurant", label: "🍽️ 点餐记录", href: "/history?scene=restaurant", disabled: false },
    { scene: "meeting", label: "📊 会议记录", href: "/history?scene=meeting", disabled: false },
  ];

  return (
    <aside className="flex h-screen w-[220px] flex-shrink-0 flex-col border-r border-zinc-200 bg-white">
      {/* Logo */}
      <div className="px-5 pt-5 pb-4">
        <Link href="/" className="text-xl font-black tracking-tight text-zinc-900">
          Offer<span className="text-indigo-500">GPT</span>
        </Link>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-1 overflow-y-auto px-3">
        {/* 主页 */}
        <div className="mb-1">
          <p className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
            主页
          </p>
          <Link
            href="/"
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
              isActive("/")
                ? "bg-indigo-50 text-indigo-600"
                : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
            }`}
          >
            <span className="text-base">🏠</span>
            首页
          </Link>
        </div>

        {/* 训练记录 */}
        <div className="mt-4 mb-1">
          <p className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
            训练记录
          </p>
          {recordLinks.map((item) => (
              <Link
                key={item.scene}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                  isRecordActive(item.scene)
                    ? "bg-indigo-50 text-indigo-600"
                    : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
                }`}
              >
                <span className="text-base">{item.label.slice(0, 2)}</span>
                {item.label.slice(3)}
              </Link>
          ))}
        </div>

        {/* 分隔线 */}
        <div className="mx-3 my-3 h-px bg-zinc-100" />

        {/* 训练 */}
        <div className="mb-1">
          <p className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
            训练
          </p>
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-zinc-500 transition-all hover:bg-zinc-50 hover:text-zinc-700"
          >
            <span className="text-base">🎯</span>
            开始训练
          </Link>
        </div>
      </nav>

      {/* 底部用户信息 + 退出 */}
      <div className="border-t border-zinc-100 px-3 py-3">
        <div className="mb-2 flex items-center gap-2 rounded-lg px-2 py-1.5">
          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-xs font-bold text-white">
            {(user?.name || user?.email || "U").charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-zinc-700">
              {user?.name || user?.email || "用户"}
            </p>
            <p className="truncate text-[10px] text-zinc-400">
              {user?.plan === "free" ? "免费版" : user?.plan || ""}
            </p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-zinc-400 transition-all hover:bg-zinc-50 hover:text-red-500"
        >
          <span>🚪</span> 退出登录
        </button>
      </div>
    </aside>
  );
}
