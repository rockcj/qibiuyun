import SceneCard from "@/components/SceneCard";

interface SceneSummary {
  scene: string;
  displayName: string;
  description: string;
  icon: string;
  color: string;
}

async function getScenes(): Promise<SceneSummary[]> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${baseUrl}/api/scenes`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.scenes || [];
  } catch {
    // Fallback: static data when backend is unavailable
    return [
      {
        scene: "interview",
        displayName: "求职面试",
        description: "模拟真实英文面试，支持简历/JD驱动、多种面试官人格和STAR分析",
        icon: "briefcase",
        color: "#4F46E5",
      },
      {
        scene: "restaurant",
        displayName: "餐厅点餐",
        description: "在餐厅场景中练习点餐、预约、投诉和结账的实用英语",
        icon: "utensils",
        color: "#F59E0B",
      },
      {
        scene: "meeting",
        displayName: "商务会议",
        description: "练习英文会议中的汇报、提问、建议和总结能力",
        icon: "presentation",
        color: "#10B981",
      },
    ];
  }
}

export default async function Home() {
  const scenes = await getScenes();

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-zinc-50 to-white dark:from-zinc-950 dark:to-black">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black tracking-tight text-zinc-900 dark:text-white">
              Offer<span className="text-indigo-500">GPT</span>
            </span>
          </div>
          <nav className="flex items-center gap-4 text-sm text-zinc-500">
            <span className="hidden sm:inline">AI Real-Scene English Speaking Coach</span>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto w-full max-w-6xl px-6 pb-16 pt-20 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight text-zinc-900 sm:text-5xl dark:text-white">
          Talk in real scenes.{" "}
          <span className="bg-gradient-to-r from-indigo-500 via-amber-500 to-emerald-500 bg-clip-text text-transparent">
            Learn from mistakes.
          </span>{" "}
          Speak better.
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-zinc-500 dark:text-zinc-400">
          选择真实场景，与 AI 角色对话：模拟面试官、餐厅服务员、会议同事……
          实时纠正发音/语法，生成可量化的口语成长报告。
        </p>

        {/* Scene cards */}
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 justify-items-center">
          {scenes.map((scene, i) => (
            <SceneCard key={scene.scene} scene={scene} index={i} />
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-zinc-200 py-8 text-center text-sm text-zinc-400 dark:border-zinc-800">
        OfferGPT · 七牛云 × XEngineer 暑期实训营 · AI 英语口语陪练
      </footer>
    </div>
  );
}
