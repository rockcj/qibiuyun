/** 认证 token 读写与校验（AuthContext、api 客户端、middleware 共用） */

export const ACCESS_TOKEN_KEY = "offergpt-access-token";
export const REFRESH_TOKEN_KEY = "offergpt-refresh-token";

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

interface JwtPayload {
  exp?: number;
  type?: string;
}

/** 解码 JWT payload（不校验签名，仅用于过期判断） */
export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

/** access token 是否在有效期内（默认预留 60 秒缓冲） */
export function isAccessTokenValid(
  token: string | null | undefined,
  leewaySeconds = 60
): boolean {
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp > now + leewaySeconds;
}

/** 从 localStorage 读取 token 对 */
export function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  try {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (accessToken && refreshToken) {
      return { accessToken, refreshToken };
    }
  } catch {
    // localStorage 不可用
  }
  return null;
}

/** 持久化 token 对，并同步 cookie 供 middleware 读取 */
export function storeTokens(tokens: AuthTokens): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
    document.cookie = `${ACCESS_TOKEN_KEY}=${tokens.accessToken};path=/;max-age=2592000;SameSite=Lax`;
  } catch {
    // ignore
  }
}

/** 清除本地 token 与 cookie */
export function clearTokens(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    document.cookie = `${ACCESS_TOKEN_KEY}=;path=/;max-age=0`;
  } catch {
    // ignore
  }
}

/** 生成清除 access token cookie 的 Set-Cookie 片段（供 middleware 使用） */
export function clearAccessTokenCookie(response: { cookies: { set: (name: string, value: string, options?: { path?: string; maxAge?: number }) => void } }): void {
  response.cookies.set(ACCESS_TOKEN_KEY, "", { path: "/", maxAge: 0 });
}

/** 为 WebSocket 地址附加 JWT access token（非 demo 模式后端必填） */
export function buildWebSocketUrlWithToken(
  baseUrl: string,
  accessToken?: string | null
): string {
  if (!accessToken) return baseUrl;
  const separator = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${separator}token=${encodeURIComponent(accessToken)}`;
}
