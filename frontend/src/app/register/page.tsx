"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";
import RegisterForm from "@/components/RegisterForm";

function RegisterContent() {
  const { t } = useLocale();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/";

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-zinc-50 to-white dark:from-zinc-950 dark:to-black">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center px-6">
          <Link href="/" className="flex items-center gap-3">
            <span className="text-2xl font-black tracking-tight text-zinc-900 dark:text-white">
              Offer<span className="text-indigo-500">GPT</span>
            </span>
          </Link>
        </div>
      </header>

      {/* Form */}
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* 品牌标语 */}
          <div className="mb-10 text-center">
            <h1 className="text-2xl font-extrabold text-zinc-900 dark:text-white">
              {t("auth.register.title")}
            </h1>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              {t("auth.register.subtitle")}
            </p>
          </div>

          {/* 卡片 */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <RegisterForm />
          </div>

          {/* 切换到登录 */}
          <p className="mt-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
            {t("auth.register.loginPrompt")}{" "}
            <Link
              href={`/login${redirectTo !== "/" ? `?redirect=${encodeURIComponent(redirectTo)}` : ""}`}
              className="font-medium text-indigo-500 hover:text-indigo-600 transition-colors"
            >
              {t("auth.register.loginLink")}
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center text-zinc-400">
        Loading...
      </div>
    }>
      <RegisterContent />
    </Suspense>
  );
}
