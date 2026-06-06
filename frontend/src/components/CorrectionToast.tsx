"use client";

import { useEffect, useState } from "react";
import { useLocale } from "@/i18n/LocaleContext";

interface CorrectionToastProps {
  /** 纠正提示内容，null 时不显示 */
  tip: { original: string; corrected: string; spokenTip: string } | null;
  /** 自动消失毫秒数，默认 5 秒 */
  autoHideMs?: number;
}

/**
 * 非模态轻纠正 Toast — 不打断对话流，自动消失。
 */
export default function CorrectionToast({ tip, autoHideMs = 5000 }: CorrectionToastProps) {
  const { t } = useLocale();
  const [visible, setVisible] = useState(false);
  const [currentTip, setCurrentTip] = useState<CorrectionToastProps["tip"]>(null);

  useEffect(() => {
    if (!tip) return;

    // 新提示到来时立即显示
    setCurrentTip(tip);
    setVisible(true);

    const timer = setTimeout(() => {
      setVisible(false);
    }, autoHideMs);

    return () => clearTimeout(timer);
  }, [tip, autoHideMs]);

  if (!visible || !currentTip) return null;

  return (
    <div className="pointer-events-none fixed bottom-24 left-1/2 z-50 -translate-x-1/2 animate-in fade-in slide-in-from-bottom-4">
      <div className="pointer-events-auto max-w-md rounded-xl border border-amber-200 bg-amber-50 px-5 py-3 shadow-lg dark:border-amber-700 dark:bg-amber-950/90">
        <p className="text-xs font-semibold text-amber-700 dark:text-amber-300">
          {t("voice.correctionToastTitle")}
        </p>
        <p className="mt-1 text-sm text-amber-900 dark:text-amber-100">
          {currentTip.spokenTip || (
            <>
              Just a tip: we say &lsquo;
              <span className="font-medium text-emerald-700 dark:text-emerald-400">
                {currentTip.corrected}
              </span>
              &rsquo; instead of &lsquo;
              <span className="line-through">{currentTip.original}</span>&rsquo;.
            </>
          )}
        </p>
      </div>
    </div>
  );
}
