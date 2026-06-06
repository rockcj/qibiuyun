"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useLocale } from "@/i18n/LocaleContext";
import PasswordInput from "@/components/PasswordInput";

export default function RegisterForm() {
  const { t } = useLocale();
  const { register } = useAuth();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // 前端校验
    if (password.length < 6) {
      setError(t("auth.register.error.passwordTooShort"));
      return;
    }
    if (password !== confirmPassword) {
      setError(t("auth.register.error.passwordMismatch"));
      return;
    }

    setLoading(true);

    try {
      await register(email, password, name);
      // 注册成功后跳转到首页
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.register.error.generic"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </div>
      )}

      {/* 邮箱 */}
      <div>
        <label
          htmlFor="reg-email"
          className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          {t("auth.login.email")}
        </label>
        <input
          id="reg-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 shadow-sm transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:placeholder-zinc-500 dark:focus:border-indigo-500 dark:focus:ring-indigo-900/30"
        />
      </div>

      {/* 姓名（选填） */}
      <div>
        <label
          htmlFor="reg-name"
          className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          {t("auth.register.name")}
        </label>
        <input
          id="reg-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("auth.register.namePlaceholder")}
          className="w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 shadow-sm transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:placeholder-zinc-500 dark:focus:border-indigo-500 dark:focus:ring-indigo-900/30"
        />
      </div>

      {/* 密码 */}
      <div>
        <label
          htmlFor="reg-password"
          className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          {t("auth.login.password")}
        </label>
        <PasswordInput
          id="reg-password"
          required
          minLength={6}
          value={password}
          onChange={setPassword}
          placeholder={t("auth.register.passwordPlaceholder")}
          showLabel={t("auth.password.show")}
          hideLabel={t("auth.password.hide")}
        />
      </div>

      {/* 确认密码 */}
      <div>
        <label
          htmlFor="reg-confirm"
          className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          {t("auth.register.confirmPassword")}
        </label>
        <PasswordInput
          id="reg-confirm"
          required
          value={confirmPassword}
          onChange={setConfirmPassword}
          placeholder="••••••"
          showLabel={t("auth.password.show")}
          hideLabel={t("auth.password.hide")}
        />
      </div>

      {/* 提交 */}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-xl bg-indigo-500 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition-all hover:bg-indigo-600 disabled:cursor-not-allowed disabled:opacity-50 dark:shadow-indigo-900/30"
      >
        {loading ? (
          <span className="inline-flex items-center gap-2">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle
                className="opacity-25"
                cx="12" cy="12" r="10"
                stroke="currentColor" strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            {t("auth.register.submitting")}
          </span>
        ) : (
          t("auth.register.submit")
        )}
      </button>
    </form>
  );
}
