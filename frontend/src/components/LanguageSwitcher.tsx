"use client";

import { useLocale } from "@/i18n/LocaleContext";

export default function LanguageSwitcher() {
  const { locale, setLocale } = useLocale();

  const toggle = () => {
    setLocale(locale === "zh" ? "en" : "zh");
  };

  return (
    <button
      onClick={toggle}
      className="fixed bottom-4 left-4 z-50 flex items-center gap-2 rounded-full border border-zinc-200 bg-white/90 px-4 py-2 text-sm font-medium text-zinc-600 shadow-sm backdrop-blur-sm transition-all hover:bg-zinc-50 hover:shadow-md hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900/90 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      aria-label={locale === "zh" ? "Switch to English" : "切换到中文"}
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
      </svg>
      <span>{locale === "zh" ? "English" : "中文"}</span>
    </button>
  );
}
