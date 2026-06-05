import HomeContent from "@/components/HomeContent";
import type { SceneCardData } from "@/components/SceneCard";

async function getScenes(): Promise<SceneCardData[]> {
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
  return <HomeContent scenes={scenes} />;
}
