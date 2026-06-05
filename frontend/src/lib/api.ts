/** 前端 API 客户端，封装与后端的 REST 调用 */

import type {
  ApiErrorBody,
  CreateSessionRequest,
  CreateSessionResponse,
  JobCreateResponse,
  ResumeUploadResponse,
  SceneFull,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** 解析后端错误响应 */
async function parseError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return body.message || `请求失败 (${res.status})`;
  } catch {
    return `请求失败 (${res.status})`;
  }
}

/** 获取场景列表（完整配置） */
export async function fetchScenes(full = true): Promise<SceneFull[]> {
  const res = await fetch(`${API_BASE}/api/scenes?full=${full}`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.scenes || [];
}

/** 上传简历文件 */
export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/resumes`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 创建 JD 并解析 */
export async function createJob(payload: {
  title: string;
  company: string;
  jdText: string;
}): Promise<JobCreateResponse> {
  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 创建训练会话 */
export async function createSession(
  payload: CreateSessionRequest
): Promise<CreateSessionResponse> {
  const res = await fetch(`${API_BASE}/api/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}
