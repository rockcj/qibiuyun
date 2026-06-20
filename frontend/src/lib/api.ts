/** 前端 API 客户端，封装与后端的 REST 调用 */

import {
  clearTokens,
  getStoredTokens,
  storeTokens,
} from "@/lib/authTokens";
import type {
  ApiErrorBody,
  CreateSessionRequest,
  CreateSessionResponse,
  JobCreateResponse,
  ListSessionsResponse,
  ResumeUploadResponse,
  SceneFull,
  SessionAnalysisResponse,
  SessionEventsResponse,
  SessionReportResponse,
} from "@/types/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

/** 从 localStorage 读取 access token */
function getAccessToken(): string | null {
  return getStoredTokens()?.accessToken ?? null;
}

/** 从 localStorage 读取 refresh token */
function getRefreshToken(): string | null {
  return getStoredTokens()?.refreshToken ?? null;
}

/** 保存新 token 对 */
function saveTokens(accessToken: string, refreshToken: string) {
  storeTokens({ accessToken, refreshToken });
}

/** 尝试用 refresh token 刷新 access token */
async function tryRefreshToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    if (res.ok) {
      const data = await res.json();
      saveTokens(data.accessToken, data.refreshToken);
      return data.accessToken;
    }
  } catch {
    // ignore
  }
  clearTokens();
  return null;
}

/**
 * 认证 fetch 包装：自动注入 Bearer token，401 时自动刷新重试。
 * 如果 demo 模式下没有 token，仍然正常发送请求（后端会回退到 demo 用户）。
 */
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let res = await fetch(url, { ...options, headers });

  // 401 时尝试刷新 token 并重试一次
  if (res.status === 401 && token) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(url, { ...options, headers });
    }
  }

  return res;
}

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
  const res = await authFetch(`${API_BASE}/api/scenes?full=${full}`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.scenes || [];
}

/** 上传简历文件 */
export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await authFetch(`${API_BASE}/api/resumes`, {
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
  const res = await authFetch(`${API_BASE}/api/jobs`, {
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
  const res = await authFetch(`${API_BASE}/api/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 获取用户历史会话列表（含分页和场景筛选） */
export async function listUserSessions(
  limit = 20,
  offset = 0,
  scene?: string
): Promise<ListSessionsResponse> {
  let url = `${API_BASE}/api/interviews?limit=${limit}&offset=${offset}`;
  if (scene) url += `&scene=${encodeURIComponent(scene)}`;
  const res = await authFetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 删除指定会话及其关联数据 */
export async function deleteSession(sessionId: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/interviews/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
}

/** 结束训练会话 */
export async function finishSession(sessionId: string): Promise<{
  sessionId: string;
  status: string;
  reportStatus: string;
}> {
  const res = await authFetch(`${API_BASE}/api/interviews/${sessionId}/finish`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 获取课后发音/语法分析汇总 */
export async function getSessionAnalysis(
  sessionId: string
): Promise<SessionAnalysisResponse> {
  const res = await authFetch(`${API_BASE}/api/interviews/${sessionId}/analysis`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 获取场景报告 */
export async function getSessionReport(
  sessionId: string
): Promise<SessionReportResponse> {
  const res = await authFetch(`${API_BASE}/api/interviews/${sessionId}/report`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 获取 VAR 时间轴事件 */
export async function getSessionEvents(
  sessionId: string
): Promise<SessionEventsResponse> {
  const res = await authFetch(`${API_BASE}/api/interviews/${sessionId}/events`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json();
}

/** 切换 ASR 模型（Mini/Max/Max Pro） */
export async function switchAsrModel(model: string): Promise<{ status: string }> {
  const res = await authFetch(`${API_BASE}/api/asr/switch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** 查询 ASR 模型加载状态 */
export async function getAsrStatus(): Promise<{
  model: string; whisperModel: string; ready: boolean; switching: boolean;
}> {
  const res = await authFetch(`${API_BASE}/api/asr/status`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
