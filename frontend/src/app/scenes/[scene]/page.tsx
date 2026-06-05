import { notFound } from "next/navigation";
import SceneContent from "@/components/SceneContent";

/* ---------- helper ---------- */
interface SceneFull {
  scene: string;
  displayName: string;
  description: string;
  topics: { topic: string; displayName: string }[];
  roleModes: { roleMode: string; displayName: string }[];
  rubric: string[];
  requiresResumeJD: boolean;
}

async function getScene(name: string): Promise<SceneFull | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${baseUrl}/api/scenes?full=true`, { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.scenes?.find((s: SceneFull) => s.scene === name) || null;
  } catch {
    return null;
  }
}

/* ---------- page ---------- */
interface Props {
  params: Promise<{ scene: string }>;
}

export default async function SceneConfigPage({ params }: Props) {
  const { scene: sceneName } = await params;
  const scene = await getScene(sceneName);

  if (!scene) {
    notFound();
  }

  return <SceneContent scene={scene} />;
}
