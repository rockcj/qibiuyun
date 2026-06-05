"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "@/i18n/LocaleContext";

/** Icon mapping – simple emoji fallback for scene icons */
const SCENE_ICONS: Record<string, string> = {
  briefcase: "💼",
  utensils: "🍽️",
  presentation: "📊",
};

export interface SceneCardData {
  scene: string;
  displayName: string;
  description: string;
  icon: string;
  color: string;
}

interface SceneCardProps {
  scene: SceneCardData;
  index: number;
}

export default function SceneCard({ scene, index }: SceneCardProps) {
  const router = useRouter();
  const { t } = useLocale();

  const handleClick = () => {
    router.push(`/scenes/${scene.scene}`);
  };

  return (
    <button
      onClick={handleClick}
      className="group relative w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-8 text-left shadow-sm transition-all duration-300 hover:shadow-xl hover:-translate-y-1 hover:border-transparent dark:border-zinc-800 dark:bg-zinc-900"
      style={{
        animationDelay: `${index * 100}ms`,
        borderColor: "transparent",
      }}
    >
      {/* Gradient border on hover */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10"
        style={{
          background: `linear-gradient(135deg, ${scene.color}22, ${scene.color}44)`,
        }}
      />

      {/* Color accent bar */}
      <div
        className="absolute top-0 left-8 right-8 h-1 rounded-b-full opacity-80"
        style={{ backgroundColor: scene.color }}
      />

      {/* Icon */}
      <div
        className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl text-2xl"
        style={{ backgroundColor: `${scene.color}18` }}
      >
        {SCENE_ICONS[scene.icon] || "🎯"}
      </div>

      {/* Title */}
      <h3 className="mb-2 text-xl font-bold text-zinc-900 dark:text-zinc-50">
        {scene.displayName}
      </h3>

      {/* Description */}
      <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400 line-clamp-2">
        {scene.description}
      </p>

      {/* CTA */}
      <div className="mt-6 flex items-center gap-2 text-sm font-medium transition-colors group-hover:opacity-100"
        style={{ color: scene.color }}
      >
        <span>{t("scene.startTraining")}</span>
        <svg className="h-4 w-4 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </button>
  );
}
